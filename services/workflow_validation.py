"""Business invariants shared by draft previews and the submission boundary."""
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation


def validate_workflow(workflow_type, fields):
    kind = getattr(workflow_type, 'value', workflow_type)
    if kind == 'leave' and fields.get('start_date') and fields.get('end_date'):
        try:
            start = date.fromisoformat(str(fields['start_date']))
            end = date.fromisoformat(str(fields['end_date']))
        except ValueError:
            raise ValueError('请提供有效的开始日期和结束日期（YYYY-MM-DD）。') from None
        if end < start:
            raise ValueError('结束日期不能早于开始日期，请修改后再提交。')
    if kind == 'reimbursement' and fields.get('amount') is not None:
        try:
            amount = Decimal(str(fields['amount']))
        except InvalidOperation:
            raise ValueError('报销金额必须是有效数字。') from None
        if not amount.is_finite() or amount <= 0:
            raise ValueError('报销金额必须大于零，请修改后再提交。')
    if kind == 'resource_booking' and fields.get('start_time') and fields.get('end_time'):
        start, end = str(fields['start_time']), str(fields['end_time'])
        if fields.get('start_date') and fields.get('end_date'):
            if 'T' not in start and ' ' not in start:
                start = f"{fields['start_date']}T{start}"
            if 'T' not in end and ' ' not in end:
                end = f"{fields['end_date']}T{end}"
        try:
            parser = datetime.fromisoformat if 'T' in start or ' ' in start else time.fromisoformat
            first, last = parser(start), parser(end)
            valid = last > first
        except (ValueError, TypeError):
            raise ValueError('预订时间格式不一致或无效，请提供同一天的时间或完整日期时间。') from None
        if not valid:
            raise ValueError('结束时间必须晚于开始时间，请修改后再提交。')
