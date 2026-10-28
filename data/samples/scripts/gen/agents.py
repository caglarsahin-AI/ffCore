"""Three agent templates (plan/13 item 3) in the plan/06 `definition` shape.

File shape {key, name, description, definition}: key/name/description are the
`agents` table columns; plan/06 defines no manifest format yet. No schema_version
(not defined in plan/06; added by 06a if needed). Runtime validation against the
06a Pydantic schema happens in 06a/13b.
"""

import json
import random
from pathlib import Path

from . import schema, write_text
from .words import HOSPITAL_NAME

# Shared blocks copied from the plan/06 example; seed-specific values (top_k,
# rag_max_tokens per profile) are applied by 06a/13b seeds, not by templates.
VARIABLES = [{"key": "hospital_name", "label": "Hastane adı", "default": HOSPITAL_NAME}]
LIMITS = {
    "max_tool_calls": 6,
    "max_turns": 10,
    "run_timeout_s": None,
    "context_tokens": 16000,
    "output_tokens": 800,
}
CONTEXT_POLICY = {
    "history_turns": 6,
    "history_summarize": True,
    "history_max_tokens": 3000,
    "memory_max_tokens": 300,
    "rag_max_tokens": 4000,
    "tools_schema_max_tokens": 1500,
    "output_reserve_tokens": 800,
    "trim_order": ["history", "rag", "memory"],
}


def _answer_rules(cite: bool, unknown: str) -> dict:
    return {
        "cite_sources": cite,
        "unknown_reply": unknown,
        "confidence_formula": "cited",
        "confidence_threshold": None,
        "show_confidence": False,
        "verify": False,
        "max_answer_tokens": 400,
    }


def _definition(
    system_prompt: str,
    knowledge: list,
    tools: list,
    approval: dict | None,
    ask_user: bool,
    limits: dict,
    answer_rules: dict,
) -> dict:
    d = {
        "model": "chat-default",
        "system_prompt": system_prompt,
        "variables": VARIABLES,
        "knowledge": knowledge,
        "tools": tools,
    }
    if approval is not None:
        d["approval"] = approval
    d.update(
        {
            "ask_user": ask_user,
            "guardrail_policy_key": "default",
            "structured_output": None,
            "limits": limits,
            "context_policy": CONTEXT_POLICY,
            "answer_rules": answer_rules,
            "reasoning": "none",
        }
    )
    return d


SQL_TOOL = {"tool_key": "mcp-sql", "actions": ["get_schema", "run_sql"]}
# PoC SQL assistant (PLAN 2d): one approved run_sql call, so the schema is in the prompt
SQL_RUN_ONLY = {"tool_key": "mcp-sql", "actions": ["run_sql"]}


def sql_schema_prompt() -> str:
    """Schema descriptions and few-shots of the demo DB, embedded in the system prompt."""
    lines = ["Veritabanı şeması (PostgreSQL, salt okunur):"]
    for table, cols in schema.TABLES:
        lines.append(f"- {table}: {schema.TABLE_DESCRIPTIONS[table]}")
        for col, _ in cols:
            desc, formula = schema.COLUMN_DESCRIPTIONS[(table, col)]
            metric = f" Ölçü: {formula}." if formula else ""
            lines.append(f"  - {col}: {desc}{metric}")
    lines.append("Örnek sorular ve SQL karşılıkları:")
    for question, sql in schema.FEW_SHOTS:
        lines.append(f"- Soru: {question}")
        lines.append(f"  SQL: {sql}")
    return "\n".join(lines)


SQL_APPROVAL = {
    "actions": ["mcp-sql.run_sql"],
    "assign_to": "analyst",
}  # A3: developer not assigned in PoC

TEMPLATES = [
    {
        "key": "sozlesme-asistani",
        "name": "Sözleşme Asistanı",
        "description": "Tedarikçi sözleşmeleri hakkındaki soruları belgelere dayanarak, kaynak "
        "göstererek cevaplar.",
        "definition": _definition(
            "Sen {{hospital_name}} için sözleşme asistanısın. Yalnızca verilen sözleşme "
            "parçalarına dayanarak cevap ver ve her bilgi için kaynak belgeyi ve maddeyi göster. "
            "Parçalarda cevap yoksa bunu açıkça söyle; tahmin yürütme.",
            knowledge=[{"kb_key": "sozlesmeler", "mode": "always", "top_k": 8, "min_score": None}],
            tools=[],
            approval=None,
            ask_user=False,
            limits=LIMITS,
            answer_rules=_answer_rules(True, "Bu bilgi belgelerde yok."),
        ),
    },
    {
        # PLAN 2d decision 5 (K-13a-0002): the PoC SQL assistant makes one approved call.
        "key": "veri-soru-cevap",
        "name": "Veri Soru-Cevap",
        "description": "Hastane işletme verisi (bölüm, yatak, yatış özeti, cihaz, arıza) "
        "hakkındaki soruları SQL ile cevaplar.",
        "definition": _definition(
            "Sen {{hospital_name}} için veri asistanısın. Aşağıdaki şemayı ve örnekleri "
            "kullanarak soruyu tek bir run_sql çağrısıyla cevapla; başka araç çağırma. Sonuçları "
            "tablo olarak yaz ve hangi sorguyu çalıştırdığını belirt. Soru belirsizse araç "
            "çağırmadan hangi bilginin eksik olduğunu yaz.\n\n" + sql_schema_prompt(),
            knowledge=[],
            tools=[SQL_RUN_ONLY],
            approval=SQL_APPROVAL,
            ask_user=False,  # plan/06: ask_user adds ask_user_question, a second tool call
            limits={**LIMITS, "max_tool_calls": 1},
            answer_rules=_answer_rules(False, "Bu soruyu mevcut veriyle cevaplayamıyorum."),
        ),
    },
    {
        "key": "karma-asistan",
        "name": "Karma Asistan",
        "description": "Sözleşme belgelerini araç olarak arar ve işletme verisini SQL ile "
        "sorgular; SQL çalıştırma onay ister.",
        "definition": _definition(
            "Sen {{hospital_name}} için sözleşme ve veri asistanısın. Sözleşme soruları için "
            "search_documents aracını, sayısal sorular için get_schema ve run_sql araçlarını "
            "kullan. Belgeden gelen bilgide kaynağı göster, veriden gelen sonucu tablo olarak yaz.",
            knowledge=[{"kb_key": "sozlesmeler", "mode": "tool", "top_k": 8, "min_score": None}],
            tools=[SQL_TOOL],
            approval=SQL_APPROVAL,
            ask_user=True,
            limits=LIMITS,
            answer_rules=_answer_rules(True, "Bu bilgi belgelerde ya da veride yok."),
        ),
    },
]


def generate(rng: random.Random, out: Path, seed: int) -> None:
    for t in TEMPLATES:
        write_text(
            out / "agents" / f"{t['key']}.json", json.dumps(t, ensure_ascii=False, indent=2) + "\n"
        )
