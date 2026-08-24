"""Patient REST endpoints adhering strictly to API_CONTRACT.md sections 4.3, 4.6, 4.11."""

import html
import json
import re
from datetime import datetime
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from src.agents.retrieval.vector import clear_patient_evidence
from src.api.dependencies import get_demo_repository
from src.api.ingestion_routes import _ingestion_service
from src.clinical.audit import AuditEvent
from src.clinical.canonical import (
    DrugInteractionFlag,
    PatientMemory,
    PatientSummary,
    ReviewResponse,
    TimelineEvent,
    TrendPoint,
)
from src.clinical.care_plan_agent import (
    CarePlanDataSummary,
    CarePlanDraft,
    CarePlanResponse,
    care_plan_agent,
)
from src.clinical.care_plan_pdf_generator import build_care_plan_pdf
from src.clinical.care_plan_share import care_plan_share_store
from src.clinical.demo_repository import DemoRepository
from src.clinical.operations import operational_store

router = APIRouter(tags=["patients"])


class PatientListResponse(BaseModel):
    items: list[PatientSummary]
    page: int
    page_size: int
    total: int


class TimelineResponse(BaseModel):
    items: list[TimelineEvent]
    data_watermark: str
    page: int
    page_size: int
    total: int


class TrendResponse(BaseModel):
    code: str
    display: str
    unit: str
    points: list[TrendPoint]
    profile_version: str = "type_2_diabetes@1.0.0"
    data_watermark: str


class DrugInteractionListResponse(BaseModel):
    items: list[DrugInteractionFlag]
    data_watermark: str


class CarePlanPdfExportRequest(BaseModel):
    plan: CarePlanDraft
    data_summary: CarePlanDataSummary
    doctor_sign_name: str = Field(default="", max_length=120)


def _validated_signer(value: str) -> str:
    signer = value.strip()
    if not signer or signer.casefold() in {"chưa ký duyệt", "chưa xác nhận"}:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "CARE_PLAN_SIGNATURE_REQUIRED",
                "message": "Bác sĩ cần ghi tên và ký duyệt trước khi phát hành bản có mã QR.",
            },
        )
    return signer


def _tts_chunks(text: str, limit: int = 180) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    chunks: list[str] = []
    for sentence in sentences:
        remaining = sentence.strip()
        while len(remaining) > limit:
            cut = remaining.rfind(" ", 0, limit + 1)
            cut = cut if cut > 40 else limit
            chunks.append(remaining[:cut].strip())
            remaining = remaining[cut:].strip()
        if remaining:
            chunks.append(remaining)
    return chunks


@router.get("/patients", response_model=PatientListResponse)
def list_patients(
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    repo: DemoRepository = Depends(get_demo_repository),
) -> PatientListResponse:
    items, total = repo.list_patients(search, page, page_size)
    return PatientListResponse(items=items, page=page, page_size=page_size, total=total)


@router.get("/patients/{patient_id}/timeline", response_model=TimelineResponse)
def get_timeline(
    patient_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    repo: DemoRepository = Depends(get_demo_repository),
) -> TimelineResponse:
    if not repo.get_patient(patient_id):
        raise HTTPException(
            status_code=404,
            detail={"code": "PATIENT_SCOPE_DENIED", "message": "Bệnh nhân không tồn tại hoặc không có quyền truy cập."},
        )

    events = repo.get_timeline(patient_id)
    total = len(events)
    start = (page - 1) * page_size
    paged = events[start:start + page_size]
    wm = repo.get_watermark(patient_id)

    return TimelineResponse(
        items=paged,
        data_watermark=wm,
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/patients/{patient_id}/trends", response_model=TrendResponse)
def get_trends(
    patient_id: str,
    code: str = Query(..., description="Mã LOINC xét nghiệm"),
    repo: DemoRepository = Depends(get_demo_repository),
) -> TrendResponse:
    if not repo.get_patient(patient_id):
        raise HTTPException(
            status_code=404,
            detail={"code": "PATIENT_SCOPE_DENIED", "message": "Bệnh nhân không tồn tại hoặc không có quyền truy cập."},
        )

    display, unit, points = repo.get_trends(patient_id, code)
    wm = repo.get_watermark(patient_id)

    return TrendResponse(
        code=code,
        display=display,
        unit=unit,
        points=points,
        profile_version="type_2_diabetes@1.0.0",
        data_watermark=wm,
    )


@router.get("/patients/{patient_id}/drug-interactions", response_model=DrugInteractionListResponse)
def get_drug_interactions(
    patient_id: str,
    repo: DemoRepository = Depends(get_demo_repository),
) -> DrugInteractionListResponse:
    if not repo.get_patient(patient_id):
        raise HTTPException(
            status_code=404,
            detail={"code": "PATIENT_SCOPE_DENIED", "message": "Bệnh nhân không tồn tại hoặc không có quyền truy cập."},
        )

    wm = repo.get_watermark(patient_id)
    return DrugInteractionListResponse(items=[], data_watermark=wm)


@router.get("/patients/{patient_id}/memory", response_model=PatientMemory)
def get_patient_memory(
    patient_id: str,
    version: int | None = None,
    repo: DemoRepository = Depends(get_demo_repository),
) -> PatientMemory:
    if not repo.get_patient(patient_id):
        raise HTTPException(
            status_code=404,
            detail={"code": "PATIENT_SCOPE_DENIED", "message": "Bệnh nhân không tồn tại hoặc không có quyền truy cập."},
        )

    memory = repo.get_patient_memory(patient_id, version)
    if not memory:
        raise HTTPException(
            status_code=404,
            detail={"code": "RESOURCE_NOT_FOUND", "message": "Chưa có bộ nhớ bệnh nhân được duyệt."},
        )
    return memory

@router.delete("/patients/{patient_id}", status_code=204)
def delete_patient(
    patient_id: str,
    repo: DemoRepository = Depends(get_demo_repository),
) -> None:
    if not repo.get_patient(patient_id):
        raise HTTPException(
            status_code=404,
            detail={"code": "PATIENT_SCOPE_DENIED", "message": "Bệnh nhân không tồn tại hoặc không có quyền truy cập."},
        )

    # 1. Delete from repository
    repo.delete_patient(patient_id)

    # 2. Delete from ingestion service and document store
    _ingestion_service.delete_for_patient(patient_id)

    # 3. Delete from vector store
    clear_patient_evidence(tenant_id="ten_demo", patient_id=patient_id)

    # 4. Audit
    try:
        from loguru import logger
        with logger.contextualize(patient_id=patient_id):
            operational_store.record(
                AuditEvent(
                    user_id="system_delete",
                    action="DELETE_PATIENT",
                    patient_id=patient_id,
                    result="SUCCESS",
                    trace_id=str(uuid4()),
                    timestamp=datetime.now(),
                )
            )
    except Exception:
        pass


def _approved_care_plan_context(
    patient_id: str,
    repo: DemoRepository,
) -> tuple[PatientSummary, ReviewResponse, PatientMemory]:
    patient = repo.get_patient(patient_id)
    if not patient:
        raise HTTPException(
            status_code=404,
            detail={"code": "PATIENT_SCOPE_DENIED", "message": "Bệnh nhân không tồn tại hoặc không có quyền truy cập."},
        )
    approved_review = repo.get_review(patient_id)
    if (
        not approved_review
        or approved_review.status != "approved"
        or not approved_review.is_current_watermark
        or approved_review.data_watermark != repo.get_watermark(patient_id)
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "REVIEW_APPROVAL_REQUIRED",
                "message": "Bác sĩ cần hoàn tất và ký duyệt bản tóm tắt hiện tại trước khi tạo phác đồ.",
            },
        )

    approved_memory = repo.get_patient_memory(patient_id, approved_review.memory_version_used)
    if (
        not approved_memory
        or approved_memory.source_review_version_id != approved_review.review_version_id
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "APPROVED_SUMMARY_UNAVAILABLE",
                "message": "Không tìm thấy bản tóm tắt đã duyệt khớp với phiên bản hiện tại.",
            },
        )
    return patient, approved_review, approved_memory


@router.post("/patients/{patient_id}/care-plan", response_model=CarePlanResponse)
async def generate_patient_care_plan(
    patient_id: str,
    repo: DemoRepository = Depends(get_demo_repository),
) -> CarePlanResponse:
    """Soạn phác đồ từ đúng bản tóm tắt đã được bác sĩ ký duyệt."""
    patient, approved_review, approved_memory = _approved_care_plan_context(patient_id, repo)

    return await care_plan_agent.generate_care_plan(
        patient=patient,
        approved_review=approved_review,
        approved_memory=approved_memory,
    )


@router.post("/patients/{patient_id}/care-plan/export.pdf")
def export_patient_care_plan_pdf(
    patient_id: str,
    payload: CarePlanPdfExportRequest,
    repo: DemoRepository = Depends(get_demo_repository),
) -> Response:
    """Export the clinician-edited care plan as a server-generated monochrome PDF."""
    patient, _, _ = _approved_care_plan_context(patient_id, repo)
    signer = _validated_signer(payload.doctor_sign_name)
    try:
        _, share_url, expires_at = care_plan_share_store.issue(
            patient_id=patient_id,
            plan=payload.plan,
            doctor_sign_name=signer,
        )
        pdf_content = build_care_plan_pdf(
            patient=patient,
            plan=payload.plan,
            data_summary=payload.data_summary,
            doctor_sign_name=signer,
            share_url=share_url,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "CARE_PLAN_PDF_FAILED", "message": "Không thể tạo file PDF hướng dẫn điều trị."},
        ) from exc

    filename = f"Huong_dan_dieu_tri_{patient_id}.pdf"
    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
            "X-Care-Plan-Listen-Url": share_url,
            "X-Care-Plan-Listen-Expires": expires_at.isoformat(),
        },
    )


@router.get("/care-plan/listen/{token}", response_class=HTMLResponse, include_in_schema=False)
def public_care_plan_listen_page(token: str) -> HTMLResponse:
    """Large-print, read-only listening page reached from the signed PDF QR."""
    record = care_plan_share_store.get(token)
    if not record:
        return HTMLResponse(
            status_code=410,
            content="""<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Hướng dẫn không còn hiệu lực</title><body style="font-family:Arial,sans-serif;max-width:680px;margin:48px auto;padding:24px;line-height:1.6"><h1>Hướng dẫn này không còn hiệu lực</h1><p>Vui lòng dùng phiếu mới nhất hoặc liên hệ cơ sở y tế để được hỗ trợ.</p><p><b>Trường hợp khẩn cấp, gọi 115.</b></p></body></html>""",
        )

    plan = record["plan"]
    sections = [
        ("Lời dặn của bác sĩ", plan.get("doctor_greeting", "")),
        ("Thuốc buổi sáng", plan.get("morning_meds", "")),
        ("Thuốc buổi tối", plan.get("evening_meds", "")),
        ("Lưu ý khi dùng thuốc", plan.get("medication_note", "")),
        ("Ăn uống", plan.get("diet_good", "")),
        ("Cần hạn chế", plan.get("diet_bad", "")),
        ("Vận động", plan.get("exercise", "")),
        ("Dấu hiệu cần cấp cứu", plan.get("emergency_warning", "")),
        ("Tái khám", plan.get("follow_up", "")),
    ]
    section_html = "".join(
        f"<section><h2>{html.escape(title)}</h2><p>{html.escape(str(value))}</p></section>"
        for title, value in sections
        if str(value).strip()
    )
    signer = html.escape(record["doctor_sign_name"])
    spoken_json = json.dumps(record.get("spoken_text", ""), ensure_ascii=False).replace("</", "<\\/")
    audio_url = f"/api/v1/care-plan/listen/{token}/audio"
    return HTMLResponse(
        content=f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Nghe hướng dẫn chăm sóc tại nhà</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;background:#f0f4f8;color:#0f172a;margin:0;padding:16px 12px 48px;line-height:1.6}}
main{{max-width:680px;margin:auto}}
header{{background:linear-gradient(135deg,#0d9488,#0f766e);color:#fff;border-radius:16px;padding:24px 20px;margin-bottom:16px;box-shadow:0 4px 12px rgba(13,148,136,0.2)}}
h1{{font-size:24px;margin:0 0 8px;line-height:1.25}}
.meta{{font-size:15px;color:#ccfbf1;margin:0}}
.audio-card{{background:#fff;border:2px solid #0d9488;border-radius:16px;padding:18px;margin-bottom:16px;box-shadow:0 4px 16px rgba(0,0,0,0.06)}}
button.primary-btn{{width:100%;min-height:58px;border:0;border-radius:12px;background:#0d9488;color:#fff;font-size:18px;font-weight:700;padding:14px;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:10px;box-shadow:0 2px 8px rgba(13,148,136,0.3);transition:background 0.2s}}
button.primary-btn:hover{{background:#0f766e}}
button.primary-btn:active{{transform:scale(0.98)}}
#speech-status{{font-size:15px;margin:12px 0 6px;color:#475569;font-weight:500;text-align:center}}
audio{{width:100%;margin-top:10px;border-radius:8px}}
section{{background:#fff;border:1px solid #e2e8f0;border-radius:14px;padding:18px 20px;margin:0 0 12px;box-shadow:0 2px 6px rgba(0,0,0,0.03)}}
h2{{font-size:18px;color:#0f766e;margin:0 0 8px;font-weight:700}}
p{{font-size:17px;margin:0;color:#334155;white-space:pre-wrap}}
.notice{{background:#fef2f2;border:2px solid #ef4444;color:#991b1b;font-weight:700;font-size:17px;border-radius:14px;padding:16px 20px;margin-top:16px}}
</style></head><body><main>
<header>
  <h1>Hướng dẫn chăm sóc tại nhà</h1>
  <p class="meta">Đã được bác sĩ <b>{signer}</b> ký duyệt.</p>
</header>

<div class="audio-card">
  <button id="play" class="primary-btn" type="button" aria-pressed="false">
    <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
    <span>BẤM ĐỂ NGHE TOÀN BỘ HƯỚNG DẪN</span>
  </button>
  <p id="speech-status" role="status">Bấm nút trên để nghe giọng đọc hướng dẫn tiếng Việt rõ ràng.</p>
  <audio id="audio-elem" src="{audio_url}" preload="metadata" controls></audio>
</div>

{section_html}

<div class="notice">
  ⚠️ Nếu có dấu hiệu nguy hiểm hoặc tình trạng nặng lên, gọi ngay 115 hoặc đến cơ sở y tế gần nhất.
</div>

<script>
const text = {spoken_json};
const audio = document.getElementById('audio-elem');
const b = document.getElementById('play');
const status = document.getElementById('speech-status');
let isAudioPlaying = false;
let isSynthSpeaking = false;

function updateButton(playing, textStr) {{
  if (playing) {{
    b.innerHTML = '<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg><span>' + textStr + '</span>';
    b.setAttribute('aria-pressed', 'true');
    b.style.background = '#e11d48';
  }} else {{
    b.innerHTML = '<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg><span>' + textStr + '</span>';
    b.setAttribute('aria-pressed', 'false');
    b.style.background = '#0d9488';
  }}
}}

audio.onplay = () => {{
  isAudioPlaying = true;
  updateButton(true, 'TẠM DỪNG PHÁT ÂM THANH');
  status.textContent = '🔊 Đang phát giọng đọc tiếng Việt từ bác sĩ...';
}};

audio.onpause = () => {{
  isAudioPlaying = false;
  updateButton(false, 'TIẾP TỤC NGHE HƯỚNG DẪN');
  status.textContent = 'Đã tạm dừng.';
}};

audio.onended = () => {{
  isAudioPlaying = false;
  updateButton(false, 'NGHE LẠI TOÀN BỘ HƯỚNG DẪN');
  status.textContent = '✅ Đã nghe xong toàn bộ hướng dẫn.';
}};

b.addEventListener('click', () => {{
  if (isAudioPlaying) {{
    audio.pause();
    return;
  }}
  
  if (isSynthSpeaking) {{
    window.speechSynthesis.cancel();
    isSynthSpeaking = false;
    updateButton(false, 'TIẾP TỤC NGHE');
    status.textContent = 'Đã dừng đọc.';
    return;
  }}

  status.textContent = 'Đang tải âm thanh...';
  audio.play().catch(err => {{
    console.warn('Audio stream fallback to SpeechSynthesis', err);
    if ('speechSynthesis' in window) {{
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = 'vi-VN';
      utterance.rate = 0.88;
      utterance.pitch = 1;
      utterance.onstart = () => {{
        isSynthSpeaking = true;
        updateButton(true, 'DỪNG ĐỌC');
        status.textContent = '🔊 Đang đọc hướng dẫn...';
      }};
      utterance.onend = () => {{
        isSynthSpeaking = false;
        updateButton(false, 'NGHE LẠI HƯỚNG DẪN');
        status.textContent = '✅ Đã đọc xong hướng dẫn.';
      }};
      utterance.onerror = () => {{
        isSynthSpeaking = false;
        updateButton(false, 'THỬ ĐỌC LẠI');
        status.textContent = 'Không thể phát giọng đọc. Vui lòng đọc nội dung văn bản bên dưới.';
      }};
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(utterance);
    }} else {{
      status.textContent = 'Không thể phát âm thanh tự động. Vui lòng đọc nội dung văn bản bên dưới.';
    }}
  }});
}});
</script>
</main></body></html>""",
        headers={"Cache-Control": "private, no-store", "X-Robots-Tag": "noindex, nofollow"},
    )


@router.get("/care-plan/listen/{token}/audio", include_in_schema=False)
async def public_care_plan_audio(token: str) -> Response:
    """Stream Vietnamese speech generated from the immutable signed snapshot."""
    record = care_plan_share_store.get(token)
    if not record:
        raise HTTPException(status_code=410, detail="Hướng dẫn này không còn hiệu lực.")
    chunks = _tts_chunks(record.get("spoken_text", ""))
    if not chunks:
        raise HTTPException(status_code=422, detail="Bản hướng dẫn chưa có nội dung để đọc.")
    url = "https://translate.google.com/translate_tts"
    headers = {"User-Agent": "Mozilla/5.0"}
    audio_parts: list[bytes] = []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            for chunk in chunks:
                response = await client.get(
                    url,
                    params={"ie": "UTF-8", "q": chunk, "tl": "vi", "client": "tw-ob"},
                    headers=headers,
                )
                response.raise_for_status()
                audio_parts.append(response.content)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Dịch vụ đọc tiếng Việt đang tạm thời gián đoạn.") from exc
    return Response(
        content=b"".join(audio_parts),
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "private, max-age=3600",
            "Content-Disposition": "inline; filename=huong-dan-da-ky-duyet.mp3",
            "X-Content-Type-Options": "nosniff",
        },
    )
