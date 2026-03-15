from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import hashlib
from typing import Iterable
import uuid

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone

from apps.accounts.validators import only_digits
from apps.employees.journey_config import WEEK_DAYS
from apps.employees.models import Employee, NSRSequence, WorkSchedule

from .models import AttendanceAdjustment, AttendanceRecord

MONTH_LABELS = {
    1: "janeiro",
    2: "fevereiro",
    3: "março",
    4: "abril",
    5: "maio",
    6: "junho",
    7: "julho",
    8: "agosto",
    9: "setembro",
    10: "outubro",
    11: "novembro",
    12: "dezembro",
}

WEEKDAY_SHORT_LABELS = {
    "SEGUNDA": "Seg",
    "TERCA": "Ter",
    "QUARTA": "Qua",
    "QUINTA": "Qui",
    "SEXTA": "Sex",
    "SABADO": "Sáb",
    "DOMINGO": "Dom",
}

ATTENDANCE_LABELS = {
    AttendanceRecord.Tipo.ENTRADA: "E",
    AttendanceRecord.Tipo.SAIDA: "S",
    AttendanceRecord.Tipo.INICIO_INTERVALO: "II",
    AttendanceRecord.Tipo.FIM_INTERVALO: "FI",
}

ADJUSTMENT_STATUS_LABELS = {
    AttendanceAdjustment.Status.PENDING: "Adicionada (Pendente)",
    AttendanceAdjustment.Status.APPROVED: "Adicionada (Aprovada)",
    AttendanceAdjustment.Status.REJECTED: "Adicionada (Rejeitada)",
    AttendanceAdjustment.Status.DISREGARDED: "Desconsiderada",
}

ADJUSTMENT_ACTION_LABELS = {
    AttendanceAdjustment.ActionType.ADD_MARK: "ADICIONAR_MARCACAO",
    AttendanceAdjustment.ActionType.DISREGARD_MARK: "DESCONSIDERAR_MARCACAO",
}


@dataclass(frozen=True)
class TreatmentPeriod:
    year: int
    month: int
    start_date: date
    end_date: date
    period_value: str
    month_label: str
    start_datetime: datetime
    end_datetime: datetime


def parse_treatment_period(raw_period: str | None, *, today: date | None = None) -> TreatmentPeriod:
    today = today or timezone.localdate()
    value = (raw_period or "").strip()
    if value:
        try:
            year_str, month_str = value.split("-", 1)
            year = int(year_str)
            month = int(month_str)
            start_date = date(year, month, 1)
        except (TypeError, ValueError) as exc:
            raise ValidationError("Informe um período válido.") from exc
    else:
        year = today.year
        month = today.month
        start_date = date(year, month, 1)

    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)

    month_label = f"{MONTH_LABELS[start_date.month]} de {start_date.year}"
    start_datetime = timezone.make_aware(datetime.combine(start_date, time.min))
    end_datetime = timezone.make_aware(datetime.combine(next_month, time.min))

    return TreatmentPeriod(
        year=year,
        month=month,
        start_date=start_date,
        end_date=next_month - timedelta(days=1),
        period_value=f"{year:04d}-{month:02d}",
        month_label=month_label,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
    )


def format_minutes_label(total_minutes: int, *, signed: bool = False) -> str:
    total_minutes = int(total_minutes or 0)
    absolute = abs(total_minutes)
    hours = absolute // 60
    minutes = absolute % 60
    label = f"{hours}h{minutes:02d}min" if hours else f"{minutes}min"
    if not signed:
        return label
    prefix = "+" if total_minutes >= 0 else "-"
    return f"{prefix}{label}"


def format_hhmm_from_minutes(total_minutes: int) -> str:
    total_minutes = int(total_minutes or 0)
    sign = "-" if total_minutes < 0 else ""
    absolute = abs(total_minutes)
    hours = absolute // 60
    minutes = absolute % 60
    return f"{sign}{hours:02d}:{minutes:02d}"


@dataclass(frozen=True)
class ExpectedDay:
    minutes: int
    first_entry_minute: int | None
    last_exit_minute: int | None
    label: str
    workday: bool


class TreatmentPointService:
    """Calcula a visão web inicial de tratamento de ponto a partir das batidas reais."""

    def list_collaborator_summaries(
        self,
        *,
        tenant,
        period: TreatmentPeriod,
        search: str = "",
        only_inconsistencies: bool = False,
        only_pendencias: bool = False,
    ) -> list[dict]:
        employees = self._employees_queryset(tenant=tenant, search=search)
        records_by_employee = self._records_grouped_by_employee(
            tenant=tenant,
            employee_ids=[employee.id for employee in employees],
            period=period,
        )
        adjustments_by_employee = self._adjustments_grouped_by_employee(
            tenant=tenant,
            employee_ids=[employee.id for employee in employees],
            period=period,
        )

        summaries = []
        for employee in employees:
            summary = self._build_employee_summary(
                employee=employee,
                period=period,
                day_records_map=records_by_employee.get(employee.id, {}),
                day_adjustments_map=adjustments_by_employee.get(employee.id, {}),
            )
            if only_inconsistencies and summary["inconsistencias_count"] <= 0:
                continue
            if only_pendencias and summary["pendencias_count"] <= 0:
                continue
            summaries.append(summary)
        return summaries

    def build_employee_mirror(self, *, tenant, employee_id: int, period: TreatmentPeriod) -> dict:
        employee = (
            Employee.all_objects.filter(tenant=tenant)
            .select_related("work_schedule")
            .get(id=employee_id)
        )
        grouped = self._records_grouped_by_employee(
            tenant=tenant,
            employee_ids=[employee.id],
            period=period,
        )
        adjustments = self._adjustments_grouped_by_employee(
            tenant=tenant,
            employee_ids=[employee.id],
            period=period,
        )
        return self._build_employee_summary(
            employee=employee,
            period=period,
            day_records_map=grouped.get(employee.id, {}),
            day_adjustments_map=adjustments.get(employee.id, {}),
            include_daily_rows=True,
        )

    def create_day_adjustment(
        self,
        *,
        tenant,
        employee_id: int,
        target_date: date,
        action: str,
        hour: str,
        motivo: str,
        requested_by=None,
        tipo: str | None = None,
    ) -> AttendanceAdjustment:
        employee = Employee.all_objects.filter(tenant=tenant).select_related("work_schedule").get(id=employee_id)

        if action != "ADICIONAR_MARCACAO":
            raise ValidationError("Ação de ajuste inválida para o MVP.")

        minute_of_day = self._to_minutes(hour)
        if minute_of_day is None:
            raise ValidationError("Dados de marcação inválidos para este dia.")

        records = self._records_for_employee_day(employee=employee, target_date=target_date)
        adjustment_type = self._resolve_adjustment_type(records=records, explicit_type=tipo)
        timestamp = timezone.make_aware(
            datetime.combine(
                target_date,
                time(hour=minute_of_day // 60, minute=minute_of_day % 60),
            )
        )
        normalized_reason = (motivo or "").strip()
        if not normalized_reason:
            raise ValidationError("Informe o motivo do ajuste.")

        payload = f"{employee.id}|{target_date.isoformat()}|{hour}|{adjustment_type}|{normalized_reason}"
        foto_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        with transaction.atomic():
            record = AttendanceRecord.all_objects.create(
                tenant=tenant,
                employee=employee,
                tipo=adjustment_type,
                timestamp=timestamp,
                nsr=self._next_safe_nsr(tenant.id),
                foto_path=f"manual://treatment-adjustment/{employee.id}/{target_date.isoformat()}",
                foto_hash=foto_hash,
                confianca_biometrica=0.0,
                origem=AttendanceRecord.Origem.ONLINE,
                justificativa=normalized_reason,
                client_event_id=f"manual-adjustment:{uuid.uuid4()}",
            )
            adjustment = AttendanceAdjustment.all_objects.create(
                tenant=tenant,
                employee=employee,
                attendance_record=record,
                action_type=AttendanceAdjustment.ActionType.ADD_MARK,
                status=AttendanceAdjustment.Status.PENDING,
                target_date=target_date,
                requested_by=requested_by,
                reason=normalized_reason,
                auto_generated=bool(requested_by is None),
            )
            adjustment.full_clean()
            adjustment.save()
        return adjustment

    def auto_adjust_period(self, *, tenant, employee_id: int, period: TreatmentPeriod, requested_by=None) -> dict:
        employee = Employee.all_objects.filter(tenant=tenant).select_related("work_schedule").get(id=employee_id)
        day_records_map = self._records_grouped_by_employee(
            tenant=tenant,
            employee_ids=[employee.id],
            period=period,
        ).get(employee.id, {})

        processed_days = 0
        updated_days = 0
        pendencias_restantes = 0

        current_date = period.start_date
        while current_date <= period.end_date:
            processed_days += 1
            records = day_records_map.get(current_date, [])
            expected = self._expected_for_day(employee.work_schedule, current_date)
            _, has_pending_exit, _ = self._worked_minutes_for_day(records)

            if has_pending_exit and expected.last_exit_minute is not None:
                hour = f"{expected.last_exit_minute // 60:02d}:{expected.last_exit_minute % 60:02d}"
                self.create_day_adjustment(
                    tenant=tenant,
                    employee_id=employee.id,
                    target_date=current_date,
                    action="ADICIONAR_MARCACAO",
                    hour=hour,
                    motivo="Ajuste automático do espelho",
                    requested_by=requested_by,
                    tipo=AttendanceRecord.Tipo.SAIDA,
                )
                updated_days += 1
            elif has_pending_exit:
                pendencias_restantes += 1

            current_date += timedelta(days=1)

        refreshed = self.build_employee_mirror(tenant=tenant, employee_id=employee.id, period=period)
        pendencias_restantes = refreshed["pendencias_count"]

        return {
            "processed_days": processed_days,
            "updated_days": updated_days,
            "pendencias_restantes": pendencias_restantes,
        }

    def decide_adjustment(
        self,
        *,
        tenant,
        adjustment_id,
        decision: str,
        decided_by=None,
        decision_note: str = "",
    ) -> AttendanceAdjustment:
        adjustment = AttendanceAdjustment.all_objects.select_related("attendance_record").get(
            tenant=tenant,
            id=adjustment_id,
        )
        if adjustment.status in {
            AttendanceAdjustment.Status.APPROVED,
            AttendanceAdjustment.Status.REJECTED,
            AttendanceAdjustment.Status.DISREGARDED,
        }:
            raise ValidationError("Não é permitido decidir um ajuste já finalizado.")

        mapping = {
            "APROVAR": AttendanceAdjustment.Status.APPROVED,
            "REJEITAR": AttendanceAdjustment.Status.REJECTED,
            "DESCONSIDERAR": AttendanceAdjustment.Status.DISREGARDED,
        }
        next_status = mapping.get((decision or "").strip().upper())
        if not next_status:
            raise ValidationError("Decisão de ajuste inválida.")

        if next_status == AttendanceAdjustment.Status.REJECTED and len((decision_note or "").strip()) < 10:
            raise ValidationError("Informe a justificativa para rejeitar o ajuste.")

        adjustment.status = next_status
        adjustment.decided_by = decided_by
        adjustment.decision_note = (decision_note or "").strip()
        adjustment.decided_at = timezone.now()
        adjustment.full_clean()
        adjustment.save(update_fields=["status", "decided_by", "decision_note", "decided_at", "updated_at"])
        return adjustment

    def adjustment_requests_summary(self, *, tenant) -> dict:
        open_statuses = [
            AttendanceAdjustment.Status.PENDING,
            AttendanceAdjustment.Status.APPROVED,
            AttendanceAdjustment.Status.REJECTED,
        ]
        base_qs = AttendanceAdjustment.all_objects.filter(tenant=tenant)
        return {
            "ajustes": {
                "pendentes": base_qs.filter(status=AttendanceAdjustment.Status.PENDING).count(),
                "total_abertas": base_qs.filter(status__in=open_statuses).count(),
            },
            "acessos": {
                "pendentes": 0,
                "total_abertas": 0,
            },
        }

    def list_adjustment_requests(
        self,
        *,
        tenant,
        status_value: str = "",
        period_start: date | None = None,
        period_end: date | None = None,
        employee_id: int | None = None,
        query: str = "",
    ) -> list[dict]:
        queryset = (
            AttendanceAdjustment.all_objects.filter(tenant=tenant)
            .select_related("employee", "requested_by", "attendance_record")
            .order_by("-created_at", "-id")
        )
        normalized_status = (status_value or "").strip().upper()
        if normalized_status and normalized_status != "TODOS":
            queryset = queryset.filter(status=normalized_status)
        if period_start:
            queryset = queryset.filter(target_date__gte=period_start)
        if period_end:
            queryset = queryset.filter(target_date__lte=period_end)
        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)
        if query:
            digits = only_digits(query)
            query_filter = Q(employee__nome__icontains=query) | Q(reason__icontains=query)
            if digits:
                query_filter |= Q(employee__cpf__icontains=digits) | Q(employee__pis__icontains=digits)
            queryset = queryset.filter(query_filter)

        return [self._serialize_adjustment_request_item(adjustment) for adjustment in queryset]

    def get_adjustment_request_detail(self, *, tenant, adjustment_id) -> dict:
        adjustment = (
            AttendanceAdjustment.all_objects.filter(tenant=tenant)
            .select_related("employee", "requested_by", "decided_by", "attendance_record", "target_record")
            .get(id=adjustment_id)
        )
        day_records = self._records_for_employee_day(employee=adjustment.employee, target_date=adjustment.target_date)
        original_markings = []
        proposed_markings = []
        for record in day_records:
            label = ATTENDANCE_LABELS.get(record.tipo, record.tipo)
            stamp = timezone.localtime(record.timestamp).strftime("%H:%M")
            if adjustment.attendance_record_id and record.id == adjustment.attendance_record_id:
                proposed_markings.append(f"{stamp} ({label})")
            else:
                original_markings.append(f"{stamp} ({label})")

        history = [
            {
                "tipo": "SOLICITADA",
                "usuario": self._display_user(adjustment.requested_by),
                "data": adjustment.created_at,
                "observacao": adjustment.reason,
            }
        ]
        if adjustment.decided_at:
            history.append(
                {
                    "tipo": adjustment.status,
                    "usuario": self._display_user(adjustment.decided_by),
                    "data": adjustment.decided_at,
                    "observacao": adjustment.decision_note,
                }
            )

        return {
            "id": str(adjustment.id),
            "protocolo": self._adjustment_protocol(adjustment),
            "status": adjustment.status,
            "marcacoes_originais": original_markings,
            "marcacoes_propostas": proposed_markings,
            "historico": history,
        }

    def _employees_queryset(self, *, tenant, search: str) -> list[Employee]:
        queryset = (
            Employee.all_objects.filter(tenant=tenant, ativo=True)
            .select_related("work_schedule")
            .order_by("nome", "id")
        )
        if search:
            digits = only_digits(search)
            query_filter = Q(nome__icontains=search)
            if digits:
                query_filter |= Q(cpf__icontains=digits) | Q(pis__icontains=digits)
            queryset = queryset.filter(query_filter)
        return list(queryset)

    def _records_grouped_by_employee(self, *, tenant, employee_ids: Iterable[int], period: TreatmentPeriod):
        if not employee_ids:
            return {}

        grouped: dict[int, dict[date, list[AttendanceRecord]]] = defaultdict(lambda: defaultdict(list))
        records = (
            AttendanceRecord.all_objects.filter(
                tenant=tenant,
                employee_id__in=list(employee_ids),
                timestamp__gte=period.start_datetime,
                timestamp__lt=period.end_datetime,
            )
            .select_related("employee")
            .order_by("employee_id", "timestamp", "id")
        )
        for record in records:
            local_timestamp = timezone.localtime(record.timestamp)
            grouped[record.employee_id][local_timestamp.date()].append(record)
        return grouped

    def _adjustments_grouped_by_employee(self, *, tenant, employee_ids: Iterable[int], period: TreatmentPeriod):
        if not employee_ids:
            return {}

        grouped: dict[int, dict[date, list[AttendanceAdjustment]]] = defaultdict(lambda: defaultdict(list))
        adjustments = (
            AttendanceAdjustment.all_objects.filter(
                tenant=tenant,
                employee_id__in=list(employee_ids),
                target_date__gte=period.start_date,
                target_date__lte=period.end_date,
            )
            .select_related("attendance_record", "target_record")
            .order_by("target_date", "created_at", "id")
        )
        for adjustment in adjustments:
            grouped[adjustment.employee_id][adjustment.target_date].append(adjustment)
        return grouped

    def _build_employee_summary(
        self,
        *,
        employee: Employee,
        period: TreatmentPeriod,
        day_records_map: dict[date, list[AttendanceRecord]],
        day_adjustments_map: dict[date, list[AttendanceAdjustment]],
        include_daily_rows: bool = False,
    ) -> dict:
        saldo_bh_min = 0
        atrasos_min = 0
        faltas_dias = 0
        pendencias_count = 0
        inconsistencias_count = 0
        total_trabalhado_min = 0
        total_previsto_min = 0
        he_50_min = 0
        he_100_min = 0
        saidas_antec_min = 0
        adicional_noturno_min = 0
        daily_rows = []

        current_date = period.start_date
        while current_date <= period.end_date:
            expected = self._expected_for_day(employee.work_schedule, current_date)
            records = day_records_map.get(current_date, [])
            adjustments = day_adjustments_map.get(current_date, [])
            effective_records, adjustment_flags = self._effective_records_for_day(records=records, adjustments=adjustments)
            actual_minutes, has_pending_exit, first_entry_minute = self._worked_minutes_for_day(effective_records)

            total_trabalhado_min += actual_minutes
            total_previsto_min += expected.minutes

            balance = actual_minutes - expected.minutes
            saldo_bh_min += balance

            occurrences = []
            row_tone = "neutral"

            if expected.workday and not records:
                faltas_dias += 1
                inconsistencias_count += 1
                occurrences.append("Sem marcações")
                row_tone = "warning"

            if has_pending_exit:
                pendencias_count += 1
                inconsistencias_count += 1
                occurrences.append("Falta saída")
                row_tone = "danger"

            if adjustment_flags["pending_count"] > 0:
                pendencias_count += adjustment_flags["pending_count"]
                occurrences.append(
                    f"{adjustment_flags['pending_count']} ajuste(s) pendente(s)"
                )
                if row_tone == "neutral":
                    row_tone = "warning"

            if expected.workday and records and actual_minutes < expected.minutes and row_tone == "neutral":
                inconsistencias_count += 1
                row_tone = "warning"

            if (
                expected.first_entry_minute is not None
                and first_entry_minute is not None
                and first_entry_minute > expected.first_entry_minute
            ):
                atrasos_min += first_entry_minute - expected.first_entry_minute

            if expected.workday and records and actual_minutes < expected.minutes:
                deficit = expected.minutes - actual_minutes
                saidas_antec_min += deficit

            if actual_minutes > expected.minutes and expected.workday:
                overtime = actual_minutes - expected.minutes
                he_50_min += overtime

            if include_daily_rows:
                daily_rows.append(
                    {
                        "date": current_date,
                        "date_label": current_date.strftime("%d/%m/%Y"),
                        "weekday_label": WEEKDAY_SHORT_LABELS[WEEK_DAYS[current_date.weekday()]],
                        "expected_label": expected.label,
                        "markings_label": self._markings_label(records=records, adjustments=adjustments),
                        "worked_label": format_hhmm_from_minutes(actual_minutes),
                        "balance_label": format_minutes_label(balance, signed=True),
                        "occurrences": occurrences,
                        "row_tone": row_tone,
                        "pending_adjustments": [
                            {
                                "id": str(adjustment.id),
                                "status": adjustment.status,
                                "reason": adjustment.reason,
                            }
                            for adjustment in adjustments
                            if adjustment.status == AttendanceAdjustment.Status.PENDING
                        ],
                    }
                )

            current_date += timedelta(days=1)

        summary = {
            "employee_id": employee.id,
            "employee": employee,
            "nome": employee.nome,
            "cargo": employee.funcao or employee.departamento or "-",
            "saldo_bh_min": saldo_bh_min,
            "saldo_bh_label": format_minutes_label(saldo_bh_min),
            "he_50_min": he_50_min,
            "he_50_label": format_minutes_label(he_50_min),
            "he_100_min": he_100_min,
            "he_100_label": format_minutes_label(he_100_min),
            "atrasos_min": atrasos_min,
            "atrasos_label": format_minutes_label(atrasos_min) if atrasos_min else "-",
            "faltas_dias": faltas_dias,
            "faltas_label": str(faltas_dias) if faltas_dias else "-",
            "pendencias_count": pendencias_count,
            "pendencias_label": str(pendencias_count) if pendencias_count else "-",
            "inconsistencias_count": inconsistencias_count,
            "total_trabalhado_min": total_trabalhado_min,
            "total_previsto_min": total_previsto_min,
            "total_trabalhado_label": format_minutes_label(total_trabalhado_min),
            "total_previsto_label": format_minutes_label(total_previsto_min),
            "saidas_antec_min": saidas_antec_min,
            "saidas_antec_label": format_minutes_label(saidas_antec_min),
            "adicional_noturno_min": adicional_noturno_min,
            "adicional_noturno_label": format_minutes_label(adicional_noturno_min),
            "period_status_label": "Aberto",
            "daily_rows": daily_rows,
        }
        return summary

    def _expected_for_day(self, schedule: WorkSchedule | None, target_date: date) -> ExpectedDay:
        if schedule is None:
            return ExpectedDay(minutes=0, first_entry_minute=None, last_exit_minute=None, label="Sem jornada", workday=False)

        config = schedule.configuracao or {}

        if schedule.tipo == WorkSchedule.TipoJornada.SEMANAL:
            day_config = self._day_config_by_weekday(config.get("dias", []), target_date)
            if not day_config or day_config.get("dsr"):
                return ExpectedDay(minutes=0, first_entry_minute=None, last_exit_minute=None, label="Folga / DSR", workday=False)
            total = self._total_minutes_from_pairs(
                [
                    (day_config.get("entrada_1"), day_config.get("saida_1")),
                    (day_config.get("entrada_2"), day_config.get("saida_2")),
                ]
            )
            return ExpectedDay(
                minutes=total,
                first_entry_minute=self._to_minutes(day_config.get("entrada_1")),
                last_exit_minute=self._to_minutes(day_config.get("saida_2")) or self._to_minutes(day_config.get("saida_1")),
                label=self._schedule_window_label(
                    [
                        (day_config.get("entrada_1"), day_config.get("saida_1")),
                        (day_config.get("entrada_2"), day_config.get("saida_2")),
                    ]
                ),
                workday=total > 0,
            )

        if schedule.tipo == WorkSchedule.TipoJornada.FRACIONADA:
            day_config = self._day_config_by_weekday(config.get("dias", []), target_date)
            if not day_config or day_config.get("dsr"):
                return ExpectedDay(minutes=0, first_entry_minute=None, last_exit_minute=None, label="Folga / DSR", workday=False)

            periods = []
            for period in day_config.get("periodos", []):
                if isinstance(period, dict):
                    periods.append((period.get("inicio"), period.get("fim")))
            return ExpectedDay(
                minutes=self._total_minutes_from_pairs(periods),
                first_entry_minute=self._to_minutes(periods[0][0]) if periods else None,
                last_exit_minute=self._to_minutes(periods[-1][1]) if periods else None,
                label=self._schedule_window_label(periods),
                workday=bool(periods),
            )

        if schedule.tipo == WorkSchedule.TipoJornada.X12X36:
            start_value = config.get("data_inicio_escala")
            try:
                start_date = datetime.strptime(start_value, "%Y-%m-%d").date()
            except (TypeError, ValueError):
                return ExpectedDay(minutes=0, first_entry_minute=None, last_exit_minute=None, label="Escala inválida", workday=False)

            day_delta = (target_date - start_date).days
            is_workday = (day_delta % 2) == 0
            if not is_workday:
                return ExpectedDay(minutes=0, first_entry_minute=None, last_exit_minute=None, label="Folga 12x36", workday=False)

            start_hhmm = config.get("horario_entrada")
            end_hhmm = config.get("horario_saida")
            duration_hours = int(config.get("duracao_turno_horas") or 12)
            return ExpectedDay(
                minutes=duration_hours * 60,
                first_entry_minute=self._to_minutes(start_hhmm),
                last_exit_minute=self._to_minutes(end_hhmm),
                label=self._schedule_window_label([(start_hhmm, end_hhmm)]),
                workday=True,
            )

        if schedule.tipo == WorkSchedule.TipoJornada.EXTERNA:
            return ExpectedDay(minutes=0, first_entry_minute=None, last_exit_minute=None, label="Jornada externa", workday=False)

        return ExpectedDay(minutes=0, first_entry_minute=None, last_exit_minute=None, label="Sem jornada", workday=False)

    def _records_for_employee_day(self, *, employee: Employee, target_date: date) -> list[AttendanceRecord]:
        start_datetime = timezone.make_aware(datetime.combine(target_date, time.min))
        end_datetime = start_datetime + timedelta(days=1)
        return list(
            AttendanceRecord.all_objects.filter(
                tenant=employee.tenant,
                employee=employee,
                timestamp__gte=start_datetime,
                timestamp__lt=end_datetime,
            ).order_by("timestamp", "id")
        )

    def _effective_records_for_day(self, *, records: list[AttendanceRecord], adjustments: list[AttendanceAdjustment]):
        added_adjustments_by_record = {
            adjustment.attendance_record_id: adjustment
            for adjustment in adjustments
            if adjustment.attendance_record_id
        }
        target_adjustments_by_record = defaultdict(list)
        for adjustment in adjustments:
            if adjustment.target_record_id:
                target_adjustments_by_record[adjustment.target_record_id].append(adjustment)

        effective_records = []
        pending_count = 0

        for record in records:
            added_adjustment = added_adjustments_by_record.get(record.id)
            if added_adjustment:
                if added_adjustment.status == AttendanceAdjustment.Status.APPROVED:
                    effective_records.append(record)
                elif added_adjustment.status == AttendanceAdjustment.Status.PENDING:
                    pending_count += 1
                continue

            target_adjustments = target_adjustments_by_record.get(record.id, [])
            disregarded = any(
                adjustment.status == AttendanceAdjustment.Status.DISREGARDED
                for adjustment in target_adjustments
            )
            if disregarded:
                continue
            effective_records.append(record)

        return effective_records, {"pending_count": pending_count}

    @staticmethod
    def _day_config_by_weekday(days_config: list[dict], target_date: date):
        weekday_key = WEEK_DAYS[target_date.weekday()]
        for day in days_config:
            if isinstance(day, dict) and day.get("dia_semana") == weekday_key:
                return day
        return None

    @staticmethod
    def _to_minutes(value: str | None):
        if not isinstance(value, str):
            return None
        try:
            hours_str, minutes_str = value.split(":", 1)
            total = (int(hours_str) * 60) + int(minutes_str)
        except (TypeError, ValueError):
            return None
        return total if 0 <= total < 24 * 60 else None

    def _total_minutes_from_pairs(self, periods: list[tuple[str | None, str | None]]) -> int:
        total = 0
        for start, end in periods:
            start_min = self._to_minutes(start)
            end_min = self._to_minutes(end)
            if start_min is None or end_min is None or end_min <= start_min:
                continue
            total += end_min - start_min
        return total

    def _schedule_window_label(self, periods: list[tuple[str | None, str | None]]) -> str:
        labels = []
        for start, end in periods:
            if start and end:
                labels.append(f"{start} às {end}")
        return " • ".join(labels) if labels else "-"

    def _worked_minutes_for_day(self, records: list[AttendanceRecord]):
        total_minutes = 0
        current_start = None
        first_entry_minute = None

        for record in records:
            local_time = timezone.localtime(record.timestamp)
            minute_of_day = local_time.hour * 60 + local_time.minute

            if first_entry_minute is None and record.tipo == AttendanceRecord.Tipo.ENTRADA:
                first_entry_minute = minute_of_day

            if record.tipo in {AttendanceRecord.Tipo.ENTRADA, AttendanceRecord.Tipo.FIM_INTERVALO}:
                if current_start is None:
                    current_start = local_time
                continue

            if record.tipo in {AttendanceRecord.Tipo.INICIO_INTERVALO, AttendanceRecord.Tipo.SAIDA}:
                if current_start is not None and local_time > current_start:
                    total_minutes += int((local_time - current_start).total_seconds() // 60)
                    current_start = None

        return total_minutes, current_start is not None, first_entry_minute

    def _resolve_adjustment_type(self, *, records: list[AttendanceRecord], explicit_type: str | None) -> str:
        if explicit_type:
            valid_types = {choice[0] for choice in AttendanceRecord.Tipo.choices}
            if explicit_type not in valid_types:
                raise ValidationError("Tipo de marcação inválido para o ajuste.")
            return explicit_type

        if not records:
            return AttendanceRecord.Tipo.ENTRADA

        last_record = records[-1]
        transition_map = {
            AttendanceRecord.Tipo.ENTRADA: AttendanceRecord.Tipo.SAIDA,
            AttendanceRecord.Tipo.INICIO_INTERVALO: AttendanceRecord.Tipo.FIM_INTERVALO,
            AttendanceRecord.Tipo.FIM_INTERVALO: AttendanceRecord.Tipo.SAIDA,
            AttendanceRecord.Tipo.SAIDA: AttendanceRecord.Tipo.ENTRADA,
        }
        return transition_map.get(last_record.tipo, AttendanceRecord.Tipo.ENTRADA)

    def _next_safe_nsr(self, tenant_id) -> int:
        sequence, _ = NSRSequence.all_objects.select_for_update().get_or_create(
            tenant_id=tenant_id,
            defaults={"ultimo_nsr": 0},
        )
        max_record_nsr = (
            AttendanceRecord.all_objects.filter(tenant_id=tenant_id).aggregate(max_nsr=Max("nsr"))["max_nsr"] or 0
        )
        next_nsr = max(sequence.ultimo_nsr, max_record_nsr) + 1
        sequence.ultimo_nsr = next_nsr
        sequence.save(update_fields=["ultimo_nsr", "updated_at"])
        return next_nsr

    def _markings_label(self, *, records: list[AttendanceRecord], adjustments: list[AttendanceAdjustment]) -> str:
        if not records:
            return "Sem marcações"

        added_adjustments_by_record = {
            adjustment.attendance_record_id: adjustment
            for adjustment in adjustments
            if adjustment.attendance_record_id
        }
        target_adjustments_by_record = defaultdict(list)
        for adjustment in adjustments:
            if adjustment.target_record_id:
                target_adjustments_by_record[adjustment.target_record_id].append(adjustment)

        labels = []
        for record in records:
            local_time = timezone.localtime(record.timestamp).strftime("%H:%M")
            label = ATTENDANCE_LABELS.get(record.tipo, record.tipo)
            added_adjustment = added_adjustments_by_record.get(record.id)
            if added_adjustment:
                labels.append(
                    f"{local_time} ({label} • {ADJUSTMENT_STATUS_LABELS.get(added_adjustment.status, added_adjustment.status)})"
                )
                continue

            target_adjustments = target_adjustments_by_record.get(record.id, [])
            if any(adjustment.status == AttendanceAdjustment.Status.DISREGARDED for adjustment in target_adjustments):
                labels.append(f"{local_time} ({label} • Desconsiderada)")
                continue

            labels.append(f"{local_time} ({label} • Original)")
        return " • ".join(labels)

    def _serialize_adjustment_request_item(self, adjustment: AttendanceAdjustment) -> dict:
        return {
            "id": str(adjustment.id),
            "protocolo": self._adjustment_protocol(adjustment),
            "employee_id": adjustment.employee_id,
            "colaborador_nome": adjustment.employee.nome,
            "data_referencia": adjustment.target_date,
            "tipo_ajuste": ADJUSTMENT_ACTION_LABELS.get(adjustment.action_type, adjustment.action_type),
            "motivo": adjustment.reason,
            "status": adjustment.status,
            "solicitado_em": adjustment.created_at,
        }

    @staticmethod
    def _adjustment_protocol(adjustment: AttendanceAdjustment) -> str:
        return f"AJ-{adjustment.created_at.strftime('%Y%m%d')}-{str(adjustment.id).split('-')[0].upper()}"

    @staticmethod
    def _display_user(user) -> str:
        if not user:
            return ""
        return f"{user.first_name} {user.last_name}".strip() or user.email
