import logging

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlmodel import Session

from app.core.config import settings
from app.db.session import engine
from app.routers import auth, budgets, categories, expenses, incomes, recurring_expenses, reports

logger = logging.getLogger("app")

app = FastAPI(title="Pay and Check API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(budgets.router)
app.include_router(categories.router)
app.include_router(expenses.router)
app.include_router(incomes.router)
app.include_router(recurring_expenses.router)
app.include_router(reports.router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        # jsonable_encoder: exc.errors() puede traer objetos ValueError crudos
        # en ctx["error"] cuando un @model_validator los lanza — no serializables
        # directo con json.dumps.
        content={"error": "validation_error", "detail": jsonable_encoder(exc.errors())},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Error no controlado en %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "internal_server_error", "detail": "Ocurrió un error inesperado."},
    )


@app.get("/health")
def health() -> dict[str, str]:
    with Session(engine) as session:
        session.exec(text("SELECT 1"))
    return {"status": "ok"}
