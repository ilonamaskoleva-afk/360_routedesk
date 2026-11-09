from __future__ import annotations

import os
from datetime import datetime, timezone
from enum import Enum
from typing import Generator

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./routedesk.db")
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class TicketStatus(str, Enum):
    new = "new"
    assigned = "assigned"
    in_progress = "in_progress"
    resolved = "resolved"
    closed = "closed"


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(80))
    department: Mapped[str] = mapped_column(String(120))
    priority: Mapped[str] = mapped_column(String(40), default="Средний")
    status: Mapped[str] = mapped_column(String(40), default=TicketStatus.new.value)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    requester: Mapped[str] = mapped_column(String(120), default="Демо-сотрудник")
    assignee: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    events: Mapped[list[TicketEvent]] = relationship(back_populates="ticket", cascade="all, delete-orphan", order_by="TicketEvent.created_at")


class TicketEvent(Base):
    __tablename__ = "ticket_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(60))
    actor: Mapped[str] = mapped_column(String(120), default="system")
    details: Mapped[str] = mapped_column(Text, default="")
    from_department: Mapped[str | None] = mapped_column(String(120), nullable=True)
    to_department: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    ticket: Mapped[Ticket] = relationship(back_populates="events")


class TicketCreate(BaseModel):
    description: str = Field(min_length=5, max_length=10000)
    title: str | None = Field(default=None, max_length=200)
    priority: str | None = Field(default=None, max_length=40)
    requester: str = Field(default="Демо-сотрудник", max_length=120)


class TicketUpdate(BaseModel):
    status: TicketStatus | None = None
    assignee: str | None = Field(default=None, max_length=120)
    actor: str = Field(default="demo-user", max_length=120)
    comment: str | None = Field(default=None, max_length=4000)


class RerouteRequest(BaseModel):
    department: str = Field(min_length=2, max_length=120)
    reason: str = Field(min_length=3, max_length=2000)
    actor: str = Field(default="demo-user", max_length=120)


class FeedbackRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2000)
    actor: str = Field(default="requester", max_length=120)


class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    description: str
    category: str
    department: str
    priority: str
    status: str
    confidence: float
    requester: str
    assignee: str | None
    created_at: datetime
    updated_at: datetime


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ticket_id: int
    event_type: str
    actor: str
    details: str
    from_department: str | None
    to_department: str | None
    created_at: datetime


class FeedbackOut(BaseModel):
    ticket_id: int
    rating: int
    comment: str | None
    actor: str
    created_at: datetime


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"), index=True)
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ClassificationOut(BaseModel):
    category: str
    department: str
    priority: str
    confidence: float
    explanation: str
    automatic_routing: bool
    note: str


class MetricsOut(BaseModel):
    total_tickets: int
    open_tickets: int
    resolved_tickets: int
    reroutes: int
    average_confidence: float | None
    feedback_average: float | None
    by_department: list[dict[str, int | str]]


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def classify(text: str, requested_priority: str | None = None) -> dict:
    """Transparent demo classifier; replace with a validated model before production use."""
    rules = [
        ("IT", "Техническая поддержка", ("проектор", "компьютер", "ноутбук", "монитор", "принтер", "wi-fi", "интернет", "сервер", "аудитория"), 0.94,
         "Обнаружены признаки технической неисправности или оборудования."),
        ("АХО", "Администрация", ("уборка", "мебель", "ремонт", "освещение", "канцтовар", "дверь", "окно", "отопление"), 0.89,
         "Обнаружены признаки административно-хозяйственного обращения."),
        ("Кадры", "HR", ("отпуск", "кадры", "справка", "трудоустройство", "зарплатный лист", "сотрудник"), 0.88,
         "Обнаружены признаки кадрового обращения."),
        ("Бухгалтерия", "Бухгалтерия", ("счет", "счёт", "оплата", "акт", "налог", "бухгалтер", "компенсация"), 0.87,
         "Обнаружены признаки финансового или бухгалтерского обращения."),
        ("Учебный отдел", "Учебный отдел", ("расписание", "экзамен", "зачет", "зачёт", "оценка", "учебный план"), 0.86,
         "Обнаружены признаки учебно-организационного обращения."),
    ]
    normalized = text.casefold()
    for category, department, keywords, confidence, explanation in rules:
        if any(word in normalized for word in keywords):
            priority = requested_priority or ("Высокий" if any(w in normalized for w in ("срочно", "сегодня", "завтра", "не работает")) else "Средний")
            return {"category": category, "department": department, "priority": priority, "confidence": confidence,
                    "explanation": explanation, "automatic_routing": confidence >= 0.90,
                    "note": "Демонстрационная rule-based классификация, не ML-модель. Низкая уверенность требует проверки человеком."}
    return {"category": "Не определено", "department": "Ручная проверка", "priority": requested_priority or "Средний",
            "confidence": 0.55, "explanation": "Недостаточно однозначных признаков; требуется ручная классификация.",
            "automatic_routing": False, "note": "Демонстрационная rule-based классификация, не ML-модель. Низкая уверенность требует проверки человеком."}


def add_event(db: Session, ticket: Ticket, event_type: str, details: str = "", actor: str = "system",
              from_department: str | None = None, to_department: str | None = None) -> None:
    db.add(TicketEvent(ticket_id=ticket.id, event_type=event_type, actor=actor, details=details,
                       from_department=from_department, to_department=to_department))


def get_ticket_or_404(db: Session, ticket_id: int) -> Ticket:
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    return ticket


app = FastAPI(title="RouteDesk API", version="0.1.0", description="MVP API для внутренних заявок, маршрутизации и аналитики")
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
Base.metadata.create_all(bind=engine)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "routedesk-api"}


@app.post("/api/classify", response_model=ClassificationOut)
def classify_endpoint(payload: TicketCreate) -> dict:
    return classify(payload.description, payload.priority)


@app.post("/api/tickets", response_model=TicketOut, status_code=201)
def create_ticket(payload: TicketCreate, db: Session = Depends(get_db)) -> Ticket:
    result = classify(payload.description, payload.priority)
    title = payload.title or payload.description.strip().splitlines()[0][:200]
    ticket = Ticket(title=title, description=payload.description, category=result["category"],
                    department=result["department"], priority=result["priority"], confidence=result["confidence"],
                    requester=payload.requester)
    db.add(ticket)
    db.flush()
    add_event(db, ticket, "created", "Заявка создана", payload.requester)
    add_event(db, ticket, "classified", result["explanation"], "routing-engine", to_department=ticket.department)
    db.commit()
    db.refresh(ticket)
    return ticket


@app.get("/api/tickets", response_model=list[TicketOut])
def list_tickets(status: TicketStatus | None = None, department: str | None = None,
                 limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0),
                 db: Session = Depends(get_db)) -> list[Ticket]:
    query = select(Ticket).order_by(Ticket.created_at.desc()).limit(limit).offset(offset)
    if status:
        query = query.where(Ticket.status == status.value)
    if department:
        query = query.where(Ticket.department == department)
    return list(db.scalars(query).all())


@app.get("/api/tickets/{ticket_id}", response_model=TicketOut)
def get_ticket(ticket_id: int, db: Session = Depends(get_db)) -> Ticket:
    return get_ticket_or_404(db, ticket_id)


@app.get("/api/tickets/{ticket_id}/events", response_model=list[EventOut])
def ticket_events(ticket_id: int, db: Session = Depends(get_db)) -> list[TicketEvent]:
    get_ticket_or_404(db, ticket_id)
    return list(db.scalars(select(TicketEvent).where(TicketEvent.ticket_id == ticket_id).order_by(TicketEvent.created_at)).all())


@app.patch("/api/tickets/{ticket_id}", response_model=TicketOut)
def update_ticket(ticket_id: int, payload: TicketUpdate, db: Session = Depends(get_db)) -> Ticket:
    ticket = get_ticket_or_404(db, ticket_id)
    changes: list[str] = []
    if payload.status and ticket.status != payload.status.value:
        old = ticket.status
        ticket.status = payload.status.value
        changes.append(f"Статус: {old} → {ticket.status}")
    if payload.assignee is not None:
        ticket.assignee = payload.assignee
        if ticket.status == TicketStatus.new.value:
            ticket.status = TicketStatus.assigned.value
        changes.append(f"Исполнитель: {payload.assignee}")
    if payload.comment:
        changes.append(f"Комментарий: {payload.comment}")
    if changes:
        ticket.updated_at = datetime.now(timezone.utc)
        add_event(db, ticket, "updated", "; ".join(changes), payload.actor)
    db.commit()
    db.refresh(ticket)
    return ticket


@app.post("/api/tickets/{ticket_id}/reroute", response_model=TicketOut)
def reroute_ticket(ticket_id: int, payload: RerouteRequest, db: Session = Depends(get_db)) -> Ticket:
    ticket = get_ticket_or_404(db, ticket_id)
    old_department = ticket.department
    ticket.department = payload.department
    ticket.status = TicketStatus.assigned.value
    ticket.updated_at = datetime.now(timezone.utc)
    add_event(db, ticket, "rerouted", payload.reason, payload.actor, old_department, payload.department)
    db.commit()
    db.refresh(ticket)
    return ticket


@app.post("/api/tickets/{ticket_id}/feedback", response_model=FeedbackOut, status_code=201)
def submit_feedback(ticket_id: int, payload: FeedbackRequest, db: Session = Depends(get_db)) -> Feedback:
    ticket = get_ticket_or_404(db, ticket_id)
    feedback = Feedback(ticket_id=ticket_id, rating=payload.rating, comment=payload.comment, actor=payload.actor)
    db.add(feedback)
    add_event(db, ticket, "feedback", f"Оценка: {payload.rating}/5", payload.actor)
    db.commit()
    db.refresh(feedback)
    return feedback


@app.get("/api/metrics", response_model=MetricsOut)
def metrics(db: Session = Depends(get_db)) -> dict:
    total = db.scalar(select(func.count(Ticket.id))) or 0
    resolved = db.scalar(select(func.count(Ticket.id)).where(Ticket.status.in_([TicketStatus.resolved.value, TicketStatus.closed.value]))) or 0
    reroutes = db.scalar(select(func.count(TicketEvent.id)).where(TicketEvent.event_type == "rerouted")) or 0
    open_count = total - resolved
    avg_confidence = db.scalar(select(func.avg(Ticket.confidence)))
    avg_feedback = db.scalar(select(func.avg(Feedback.rating)))
    departments = db.execute(select(Ticket.department, func.count(Ticket.id)).group_by(Ticket.department).order_by(Ticket.department)).all()
    return {"total_tickets": total, "open_tickets": open_count, "resolved_tickets": resolved, "reroutes": reroutes,
            "average_confidence": round(avg_confidence, 3) if avg_confidence is not None else None,
            "feedback_average": round(avg_feedback, 2) if avg_feedback is not None else None,
            "by_department": [{"department": department, "count": count} for department, count in departments]}
