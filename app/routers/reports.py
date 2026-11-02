import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app import auth, crud, models, schemas
from app.database import get_db
from app.services.errors_i18n import err
from app.services.report_generator import extract_blocks, generate_report, split_for_discord

router = APIRouter(tags=["reports"])


def _to_report_out(report: models.Report) -> schemas.ReportOut:
    discord_paragraphs = (report.discord_content or report.markdown_content).split("\n\n")
    return schemas.ReportOut(
        id=report.id,
        facility_id=report.facility_id,
        generated_at=report.generated_at,
        markdown_content=report.markdown_content,
        blocks=extract_blocks(report.markdown_content),
        parts=split_for_discord(discord_paragraphs, lang=report.lang),
        created_by_name=report.created_by.name if report.created_by else None,
    )


@router.post("/api/facilities/{facility_id}/reports", response_model=schemas.ReportOut, status_code=201)
def create_report(
    facility_id: int, request: Request, lang: str = "pt-BR", catalog_lang: str | None = None, db: Session = Depends(get_db)
):
    facility = crud.get_facility(db, facility_id)
    if not facility:
        raise HTTPException(status_code=404, detail=err("facility_not_found", lang))

    stock_by_building = crud.get_current_stock_for_facility(db, facility_id)
    all_resources = crud.get_resources(db)
    targets = crud.get_facility_targets(db, facility_id)
    result = generate_report(
        facility, stock_by_building, all_resources, targets, lang=lang, catalog_lang=catalog_lang or lang
    )

    report = crud.create_report(
        db,
        facility_id=facility_id,
        markdown_content=result["markdown_content"],
        stock_snapshot=json.dumps(result["snapshot"], ensure_ascii=False),
        discord_content=result["discord_content"],
        lang=lang,
        created_by_id=auth.current_user_id(request),
    )
    return schemas.ReportOut(
        id=report.id,
        facility_id=report.facility_id,
        generated_at=report.generated_at,
        markdown_content=report.markdown_content,
        blocks=schemas.ReportBlocks(**result["blocks"]),
        parts=result["parts"],
        created_by_name=report.created_by.name if report.created_by else None,
    )


@router.get("/api/facilities/{facility_id}/reports", response_model=list[schemas.ReportOut])
def list_reports(facility_id: int, lang: str = "pt-BR", db: Session = Depends(get_db)):
    if not crud.get_facility(db, facility_id):
        raise HTTPException(status_code=404, detail=err("facility_not_found", lang))
    return [_to_report_out(r) for r in crud.get_reports(db, facility_id)]


@router.get("/api/reports/{report_id}", response_model=schemas.ReportOut)
def get_report(report_id: int, lang: str = "pt-BR", db: Session = Depends(get_db)):
    report = crud.get_report(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail=err("report_not_found", lang))
    return _to_report_out(report)


@router.delete("/api/reports/{report_id}", status_code=204)
def delete_report(report_id: int, lang: str = "pt-BR", db: Session = Depends(get_db)):
    report = crud.get_report(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail=err("report_not_found", lang))
    crud.delete_report(db, report)
