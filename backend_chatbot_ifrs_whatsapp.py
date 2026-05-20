"""
Backend Python para Chatbot WhatsApp - IFRS Campus Zona Norte
Framework: FastAPI
Banco: SQLite via SQLAlchemy

Como rodar:
1. pip install fastapi uvicorn sqlalchemy pydantic python-dotenv httpx
2. crie um arquivo .env com:
   VERIFY_TOKEN=meu_token_de_verificacao
   WHATSAPP_TOKEN=token_da_api_whatsapp
   WHATSAPP_PHONE_NUMBER_ID=id_do_numero_meta
   PROVIDER=meta
3. uvicorn backend_chatbot_ifrs_whatsapp:app --reload

Observação:
- O envio ativo está preparado para WhatsApp Cloud API da Meta.
- Para Z-API, Twilio ou outro provedor, basta adaptar a função send_whatsapp_message().
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
import os

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, Request, HTTPException, Query
from fastapi.responses import PlainTextResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker, Session

load_dotenv()

# =====================================================
# CONFIGURAÇÕES
# =====================================================

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "ifrs_zona_norte_token")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
PROVIDER = os.getenv("PROVIDER", "meta")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ifrs_chatbot.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

app = FastAPI(
    title="Chatbot IFRS Campus Zona Norte",
    description="Backend para atendimento digital via WhatsApp sobre cursos, inscrições e interessados.",
    version="1.0.0",
)


# =====================================================
# BANCO DE DADOS
# =====================================================

class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(255), nullable=True)
    telefone = Column(String(50), nullable=False, index=True)
    curso_interesse = Column(String(255), nullable=True)
    ensino_medio_concluido = Column(Boolean, nullable=True)
    bairro_cidade = Column(String(255), nullable=True)
    consentimento_lgpd = Column(Boolean, default=False)
    etapa = Column(String(100), default="inicio")
    ultima_mensagem = Column(Text, nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(255), nullable=False)
    modalidade = Column(String(255), nullable=True)
    requisito = Column(Text, nullable=True)
    formato = Column(String(100), nullable=True)
    gratuito = Column(Boolean, default=True)
    vagas = Column(Integer, nullable=True)
    ingresso = Column(String(100), nullable=True)
    formas_selecao = Column(Text, nullable=True)
    inscricoes = Column(String(255), nullable=True)
    observacao = Column(Text, nullable=True)
    ativo = Column(Boolean, default=True)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =====================================================
# SEED INICIAL DOS CURSOS
# =====================================================

def seed_courses():
    db = SessionLocal()
    try:
        exists = db.query(Course).filter(Course.nome.ilike("%Enfermagem%")).first()
        if not exists:
            course = Course(
                nome="Técnico em Enfermagem",
                modalidade="Técnico subsequente ao Ensino Médio",
                requisito="Ensino Médio completo",
                formato="Presencial",
                gratuito=True,
                vagas=36,
                ingresso="2026/2",
                formas_selecao="Prova presencial ou nota do Enem a partir de 2020",
                inscricoes="Período divulgado: 23/04/2026 a 04/05/2026",
                observacao=(
                    "As datas e condições podem mudar conforme edital. "
                    "Consulte sempre o site oficial do IFRS e o portal de ingresso."
                ),
                ativo=True,
            )
            db.add(course)
            db.commit()
    finally:
        db.close()


seed_courses()


# =====================================================
# MODELOS API ADMINISTRATIVA
# =====================================================

class CourseCreate(BaseModel):
    nome: str
    modalidade: Optional[str] = None
    requisito: Optional[str] = None
    formato: Optional[str] = None
    gratuito: bool = True
    vagas: Optional[int] = None
    ingresso: Optional[str] = None
    formas_selecao: Optional[str] = None
    inscricoes: Optional[str] = None
    observacao: Optional[str] = None
    ativo: bool = True


class LeadUpdate(BaseModel):
    nome: Optional[str] = None
    curso_interesse: Optional[str] = None
    ensino_medio_concluido: Optional[bool] = None
    bairro_cidade: Optional[str] = None
    consentimento_lgpd: Optional[bool] = None


# =====================================================
# SERVIÇO DE ENVIO WHATSAPP
# =====================================================

async def send_whatsapp_message(to: str, text: str) -> Dict[str, Any]:
    """
    Envia mensagem via WhatsApp Cloud API da Meta.
    Para outro provedor, substituir esta função mantendo a assinatura.
    """
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        print(f"[MODO DESENVOLVIMENTO] Para {to}: {text}")
        return {"status": "dev_mode", "to": to, "text": text}

    url = f"https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()


# =====================================================
# MOTOR DE CONVERSA
# =====================================================

class Intent(str, Enum):
    cursos = "cursos"
    inscricoes = "inscricoes"
    requisitos = "requisitos"
    vagas = "vagas"
    localizacao = "localizacao"
    humano = "humano"
    interesse = "interesse"
    saudacao = "saudacao"
    desconhecido = "desconhecido"


def normalize(text: str) -> str:
    return text.lower().strip()


def detect_intent(text: str) -> Intent:
    msg = normalize(text)

    if any(p in msg for p in ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite", "menu"]):
        return Intent.saudacao
    if any(p in msg for p in ["curso", "cursos", "tem o que", "oferta"]):
        return Intent.cursos
    if any(p in msg for p in ["inscrição", "inscricao", "inscrever", "edital", "processo seletivo"]):
        return Intent.inscricoes
    if any(p in msg for p in ["requisito", "precisa", "ensino médio", "ensino medio", "quem pode"]):
        return Intent.requisitos
    if any(p in msg for p in ["vaga", "vagas", "quantas"]):
        return Intent.vagas
    if any(p in msg for p in ["onde fica", "endereço", "endereco", "local", "localização", "localizacao"]):
        return Intent.localizacao
    if any(p in msg for p in ["humano", "atendente", "secretaria", "falar com", "contato"]):
        return Intent.humano
    if any(p in msg for p in ["tenho interesse", "quero receber", "me avise", "avisar", "cadastro"]):
        return Intent.interesse

    return Intent.desconhecido


def get_or_create_lead(db: Session, phone: str) -> Lead:
    lead = db.query(Lead).filter(Lead.telefone == phone).first()
    if not lead:
        lead = Lead(telefone=phone, etapa="inicio")
        db.add(lead)
        db.commit()
        db.refresh(lead)
    return lead


def list_courses_text(db: Session) -> str:
    courses = db.query(Course).filter(Course.ativo == True).all()
    if not courses:
        return "No momento não há cursos cadastrados na base do chatbot. Consulte o site oficial do IFRS para informações atualizadas."

    lines = ["Cursos atualmente cadastrados para o IFRS Campus Zona Norte:\n"]
    for c in courses:
        lines.append(
            f"• {c.nome}\n"
            f"  Modalidade: {c.modalidade or 'não informada'}\n"
            f"  Formato: {c.formato or 'não informado'}\n"
            f"  Gratuito: {'sim' if c.gratuito else 'não informado'}\n"
        )
    lines.append("Deseja saber sobre inscrições, vagas ou requisitos?")
    return "\n".join(lines)


def course_detail_text(db: Session, field: str) -> str:
    course = db.query(Course).filter(Course.ativo == True).first()
    if not course:
        return "Não encontrei curso ativo cadastrado. Recomendo consultar o site oficial do IFRS."

    if field == "inscricoes":
        return (
            f"Sobre inscrições para {course.nome}:\n"
            f"{course.inscricoes or 'Não há período de inscrição cadastrado no momento.'}\n\n"
            "As informações podem mudar conforme edital. Consulte sempre o portal oficial de ingresso do IFRS."
        )
    if field == "requisitos":
        return (
            f"Requisitos para {course.nome}:\n"
            f"{course.requisito or 'Requisito não cadastrado.'}\n\n"
            "Deseja que eu registre seu interesse para futuras turmas?"
        )
    if field == "vagas":
        return (
            f"Vagas para {course.nome}:\n"
            f"{course.vagas if course.vagas is not None else 'Quantidade não cadastrada'} vagas.\n\n"
            "A quantidade pode mudar conforme edital vigente."
        )

    return list_courses_text(db)


def menu_text() -> str:
    return (
        "Olá! Sou o atendimento digital do IFRS Campus Zona Norte.\n\n"
        "Posso ajudar com:\n"
        "1 - Cursos disponíveis\n"
        "2 - Inscrições e editais\n"
        "3 - Requisitos\n"
        "4 - Vagas\n"
        "5 - Localização\n"
        "6 - Registrar interesse\n"
        "7 - Falar com atendimento humano\n\n"
        "Digite uma opção ou escreva sua dúvida."
    )


def handle_registration_flow(db: Session, lead: Lead, message: str) -> str:
    msg = message.strip()

    if lead.etapa == "coletar_nome":
        lead.nome = msg
        lead.etapa = "coletar_curso"
        db.commit()
        return "Obrigado. Qual curso você tem interesse?"

    if lead.etapa == "coletar_curso":
        lead.curso_interesse = msg
        lead.etapa = "coletar_bairro"
        db.commit()
        return "Perfeito. Informe sua cidade e bairro, por gentileza."

    if lead.etapa == "coletar_bairro":
        lead.bairro_cidade = msg
        lead.etapa = "coletar_ensino_medio"
        db.commit()
        return "Você já concluiu o Ensino Médio? Responda SIM ou NÃO."

    if lead.etapa == "coletar_ensino_medio":
        if normalize(msg) in ["sim", "s", "já", "ja"]:
            lead.ensino_medio_concluido = True
        elif normalize(msg) in ["não", "nao", "n"]:
            lead.ensino_medio_concluido = False
        else:
            return "Não entendi. Você já concluiu o Ensino Médio? Responda SIM ou NÃO."

        lead.etapa = "coletar_lgpd"
        db.commit()
        return (
            "Para registrar seu interesse, precisamos do seu consentimento para guardar seus dados de contato "
            "e curso de interesse, exclusivamente para comunicação sobre cursos e processos seletivos do IFRS.\n\n"
            "Você autoriza? Responda SIM ou NÃO."
        )

    if lead.etapa == "coletar_lgpd":
        if normalize(msg) in ["sim", "s", "autorizo", "aceito"]:
            lead.consentimento_lgpd = True
            lead.etapa = "finalizado"
            db.commit()
            return (
                "Perfeito, registrei seu interesse. Assim que houver nova oportunidade ou edital aberto, "
                "a equipe poderá utilizar essas informações para contato, conforme as regras de proteção de dados."
            )
        if normalize(msg) in ["não", "nao", "n"]:
            lead.consentimento_lgpd = False
            lead.etapa = "inicio"
            db.commit()
            return "Tudo bem. Sem o consentimento, não farei o registro dos dados. Posso ajudar com outra informação?"

        return "Não entendi. Você autoriza o registro dos dados para contato sobre cursos? Responda SIM ou NÃO."

    return "Vamos registrar seu interesse. Informe seu nome completo, por gentileza."


def generate_reply(db: Session, phone: str, message: str) -> str:
    lead = get_or_create_lead(db, phone)
    lead.ultima_mensagem = message
    db.commit()

    if lead.etapa in [
        "coletar_nome",
        "coletar_curso",
        "coletar_bairro",
        "coletar_ensino_medio",
        "coletar_lgpd",
    ]:
        return handle_registration_flow(db, lead, message)

    msg = normalize(message)

    if msg == "1":
        return list_courses_text(db)
    if msg == "2":
        return course_detail_text(db, "inscricoes")
    if msg == "3":
        return course_detail_text(db, "requisitos")
    if msg == "4":
        return course_detail_text(db, "vagas")
    if msg == "5":
        return "O IFRS Campus Zona Norte fica na Av. Francisco Trein, 326, Bairro Cristo Redentor, Porto Alegre/RS."
    if msg == "6":
        lead.etapa = "coletar_nome"
        db.commit()
        return "Vamos registrar seu interesse. Informe seu nome completo, por gentileza."
    if msg == "7":
        return (
            "Posso encaminhar sua solicitação para atendimento da equipe responsável. "
            "Por favor, informe nome, telefone e o assunto."
        )

    intent = detect_intent(message)

    if intent == Intent.saudacao:
        return menu_text()
    if intent == Intent.cursos:
        return list_courses_text(db)
    if intent == Intent.inscricoes:
        return course_detail_text(db, "inscricoes")
    if intent == Intent.requisitos:
        return course_detail_text(db, "requisitos")
    if intent == Intent.vagas:
        return course_detail_text(db, "vagas")
    if intent == Intent.localizacao:
        return "O IFRS Campus Zona Norte fica na Av. Francisco Trein, 326, Bairro Cristo Redentor, Porto Alegre/RS."
    if intent == Intent.humano:
        return (
            "Certo. Para atendimento humano, informe nome, telefone e o assunto. "
            "A equipe responsável poderá dar sequência ao atendimento."
        )
    if intent == Intent.interesse:
        lead.etapa = "coletar_nome"
        db.commit()
        return "Vamos registrar seu interesse. Informe seu nome completo, por gentileza."

    return (
        "Não consegui identificar exatamente sua dúvida.\n\n"
        "Digite uma das opções:\n"
        "1 - Cursos\n"
        "2 - Inscrições\n"
        "3 - Requisitos\n"
        "4 - Vagas\n"
        "5 - Localização\n"
        "6 - Registrar interesse\n"
        "7 - Atendimento humano"
    )


# =====================================================
# WEBHOOK WHATSAPP - META CLOUD API
# =====================================================

@app.get("/webhook", response_class=PlainTextResponse)
def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return hub_challenge
    raise HTTPException(status_code=403, detail="Token de verificação inválido")


@app.post("/webhook")
async def receive_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.json()

    try:
        entry = payload.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            return JSONResponse({"status": "ignored", "reason": "no_messages"})

        message = messages[0]
        phone = message.get("from")
        text = message.get("text", {}).get("body", "")

        if not phone or not text:
            return JSONResponse({"status": "ignored", "reason": "empty_message"})

        reply = generate_reply(db, phone, text)
        await send_whatsapp_message(phone, reply)

        return JSONResponse({"status": "ok"})

    except Exception as exc:
        print("Erro ao processar webhook:", exc)
        return JSONResponse({"status": "error", "detail": str(exc)}, status_code=500)


# =====================================================
# ROTAS ADMINISTRATIVAS SIMPLES
# =====================================================

@app.get("/")
def root():
    return {
        "app": "Chatbot IFRS Campus Zona Norte",
        "status": "online",
        "docs": "/docs",
    }


@app.get("/admin/courses")
def list_courses(db: Session = Depends(get_db)):
    courses = db.query(Course).order_by(Course.id.desc()).all()
    return courses


@app.post("/admin/courses")
def create_course(course: CourseCreate, db: Session = Depends(get_db)):
    item = Course(**course.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@app.put("/admin/courses/{course_id}")
def update_course(course_id: int, course: CourseCreate, db: Session = Depends(get_db)):
    item = db.query(Course).filter(Course.id == course_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Curso não encontrado")

    for key, value in course.model_dump().items():
        setattr(item, key, value)

    db.commit()
    db.refresh(item)
    return item


@app.get("/admin/leads")
def list_leads(db: Session = Depends(get_db)):
    leads = db.query(Lead).order_by(Lead.criado_em.desc()).all()
    return leads


@app.get("/admin/leads/{lead_id}")
def get_lead(lead_id: int, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Interessado não encontrado")
    return lead


@app.put("/admin/leads/{lead_id}")
def update_lead(lead_id: int, data: LeadUpdate, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Interessado não encontrado")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(lead, key, value)

    db.commit()
    db.refresh(lead)
    return lead


# =====================================================
# ROTA DE TESTE LOCAL SEM WHATSAPP
# =====================================================

class TestMessage(BaseModel):
    telefone: str
    mensagem: str


@app.post("/test/chat")
def test_chat(data: TestMessage, db: Session = Depends(get_db)):
    resposta = generate_reply(db, data.telefone, data.mensagem)
    return {
        "telefone": data.telefone,
        "mensagem": data.mensagem,
        "resposta": resposta,
    }