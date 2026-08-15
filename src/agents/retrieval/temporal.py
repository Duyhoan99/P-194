from typing import Literal, Any
from datetime import datetime
import re
from pydantic import BaseModel

class TemporalQuery(BaseModel):
    intent: Literal["latest", "earliest", "previous", "before", "after", "between", "trend", "none"]
    target_time: datetime | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    k: int = 1

def _parse_time(time_str: str | None) -> datetime | None:
    if not time_str:
        return None
    time_str = time_str.strip()
    from datetime import timezone
    # Try DD/MM/YYYY
    m = re.match(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$", time_str)
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)), tzinfo=timezone.utc)
        except ValueError:
            pass
    # Try YYYY-MM-DD
    m = re.match(r"^(\d{4})[/.-](\d{1,2})[/.-](\d{1,2})$", time_str)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
        except ValueError:
            pass
    try:
        dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None

def filter_temporal(evidence_items: list[Any], query: TemporalQuery) -> list[Any]:
    """
    Filter and sort evidence items deterministically based on temporal intent.
    Operates on EvidenceItem or any object with a 'source_time' string attribute.
    """
    valid_items = []
    for item in evidence_items:
        if hasattr(item, "item") and hasattr(item.item, "source_time"):
            t_str = item.item.source_time
        else:
            t_str = getattr(item, "source_time", None) or (item.get("source_time") if isinstance(item, dict) else None)
        t_val = _parse_time(t_str)
        if t_val:
            valid_items.append((t_val, item))

    # Default sort by time ascending
    valid_items.sort(key=lambda x: x[0])

    if query.intent == "earliest":
        return [item for _, item in valid_items[:query.k]]
    
    if query.intent == "latest":
        valid_items.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in valid_items[:query.k]]
        
    if query.intent == "previous":
        valid_items.sort(key=lambda x: x[0], reverse=True)
        if not valid_items:
            return []
        dates = []
        for t, _ in valid_items:
            d = t.date()
            if not dates or dates[-1] != d:
                dates.append(d)
        if len(dates) < 2:
            return []
        previous_date = dates[1]
        previous_items = [(t, item) for t, item in valid_items if t.date() == previous_date]
        return [item for _, item in previous_items[:query.k]]
        
    if query.intent == "before":
        target = query.target_time or query.end_time
        if target:
            filtered = [(t, i) for t, i in valid_items if t < target]
            if not filtered:
                return []
            filtered.sort(key=lambda x: x[0], reverse=True) # closest first
            latest_date = filtered[0][0].date()
            same_day_items = [i for t, i in filtered if t.date() == latest_date]
            return same_day_items[:query.k]
        
    if query.intent == "after":
        target = query.target_time or query.start_time
        if target:
            filtered = [(t, i) for t, i in valid_items if t > target]
            if not filtered:
                return []
            filtered.sort(key=lambda x: x[0]) # closest first
            earliest_date = filtered[0][0].date()
            same_day_items = [i for t, i in filtered if t.date() == earliest_date]
            return same_day_items[:query.k]
        
    if query.intent == "between" and query.start_time and query.end_time:
        filtered = [(t, i) for t, i in valid_items if query.start_time <= t <= query.end_time]
        return [item for _, item in filtered]
        
    if query.intent == "trend":
        # Return chronologically ordered
        return [item for _, item in valid_items]

    return [item for _, item in valid_items]


def filter_comparison_endpoints(
    evidence_items: list[Any], *, relative_months: int | None = None
) -> list[Any]:
    """Return only the two requested longitudinal endpoints for each lab concept."""
    dated: list[tuple[datetime, Any, str]] = []
    for item in evidence_items:
        fact_type = str(getattr(item, "fact_type", "")).casefold()
        if "trend" in fact_type:
            continue
        source = getattr(item, "source_value", {})
        title = str(source.get("title", "")) if isinstance(source, dict) else ""
        concept = re.sub(r"^(xét nghiệm|lab)\s*:\s*", "", title.casefold()).strip()
        when = _parse_time(getattr(item, "source_time", None))
        if concept and when:
            dated.append((when, item, concept))
    if not dated:
        return []
    latest = max(row[0] for row in dated)
    months = relative_months or 6
    target_ordinal = latest.toordinal() - months * 30
    selected: list[Any] = []
    for concept in sorted({row[2] for row in dated}):
        rows = [row for row in dated if row[2] == concept]
        newest = max(rows, key=lambda row: row[0])
        older_rows = [row for row in rows if row[0] < newest[0]]
        if not older_rows:
            continue
        older = min(older_rows, key=lambda row: abs(row[0].toordinal() - target_ordinal))
        selected.extend((older[1], newest[1]))
    return selected
