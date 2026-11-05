"""Turn schemas and a stdlib-only validator for the debate engine (SPEC section 2, GOVERNANCE R5).

Research and demonstration software. Not a medical device. Synthetic cases only.
The validator supports only the JSON-Schema keywords used below.
"""
import re

_EVREF = {"type": "string", "pattern": r"^(E[0-9]+|NONE)$"}
_TEXT = {"type": "string", "minLength": 1}
_TEXTS = {"type": "array", "items": _TEXT}

_COMMON = {
    "round": {"type": "integer", "minimum": 1, "maximum": 6},
    "turn_id": _TEXT,
    "model_id": _TEXT,
    "seed": {"type": "integer"},
}
_COMMON_REQ = ["role", "round", "turn_id", "model_id", "seed"]

REPLY = {
    "type": "object", "additionalProperties": False,
    "required": ["objection_id", "response", "text", "evidence_ref"],
    "properties": {
        "objection_id": {"type": "string", "pattern": r"^O[0-9]+$"},
        "response": {"type": "string", "enum": ["accept", "rebut", "partly"]},
        "text": _TEXT, "evidence_ref": _EVREF,
    },
}

# A critic may withdraw an objection it raised earlier (SPEC section 3: "mark old ones resolved").
# objection_id is the run-wide id from the registry (the same id the proposer replies to).
WITHDRAWAL = {
    "type": "object", "additionalProperties": False,
    "required": ["objection_id", "reason"],
    "properties": {
        "objection_id": {"type": "string", "pattern": r"^O[0-9]+$"},
        "reason": _TEXT,
    },
}

PROPOSER = {
    "type": "object", "additionalProperties": False,
    "required": _COMMON_REQ + ["diagnosis", "plan", "claims", "changes_since_last_round", "open_gaps"],
    "properties": dict(_COMMON, **{
        "role": {"type": "string", "enum": ["proposer"]},
        "diagnosis": {
            "type": "object", "additionalProperties": False,
            "required": ["leading", "alternatives", "confidence"],
            "properties": {
                "leading": _TEXT, "alternatives": _TEXTS,
                "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
            },
        },
        "plan": {"type": "array", "minItems": 1, "items": {
            "type": "object", "additionalProperties": False,
            "required": ["step", "why"], "properties": {"step": _TEXT, "why": _TEXT}}},
        "claims": {"type": "array", "minItems": 1, "items": {
            "type": "object", "additionalProperties": False,
            "required": ["id", "text", "evidence_ref"],
            "properties": {"id": {"type": "string", "pattern": r"^C[0-9]+$"},
                           "text": _TEXT, "evidence_ref": _EVREF}}},
        "changes_since_last_round": _TEXTS,
        "open_gaps": _TEXTS,
        # Round 2 and later: one reply per objection (SPEC section 2, "Proposer reply").
        "replies": {"type": "array", "items": REPLY},
    }),
}


def _critic(role, types):
    return {
        "type": "object", "additionalProperties": False,
        "required": _COMMON_REQ + ["objections", "no_new_objection"],
        "properties": dict(_COMMON, **{
            "role": {"type": "string", "enum": [role]},
            "objections": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "required": ["id", "target_claim", "type", "text", "severity", "evidence_ref"],
                "properties": {
                    "id": {"type": "string", "pattern": r"^O[0-9]+$"},
                    "target_claim": {"type": "string", "pattern": r"^C[0-9]+$"},
                    "type": {"type": "string", "enum": types},
                    "text": _TEXT,
                    "severity": {"type": "string", "enum": ["minor", "major", "critical"]},
                    "evidence_ref": _EVREF,
                }}},
            "no_new_objection": {"type": "boolean"},
            "withdrawals": {"type": "array", "items": WITHDRAWAL},
        }),
    }


CRITIC_DX = _critic("critic_dx", ["missed_differential", "anchoring", "premature_closure",
                                  "logic_gap", "unsupported_claim", "other"])
CRITIC_PLAN = _critic("critic_plan", ["dose_or_drug", "interaction", "contraindication",
                                      "missing_step", "harm_risk", "unsupported_claim", "other"])

# Stop record. Written by CODE (SPEC section 3), never by a model. Same validator checks the log.
STOP = {
    "type": "object", "additionalProperties": False,
    "required": ["role", "round", "status", "reason", "new_objections_this_round"],
    "properties": {
        "role": {"type": "string", "enum": ["stop"]},
        "round": {"type": "integer", "minimum": 1, "maximum": 6},
        "status": {"type": "string", "enum": ["converged", "max_rounds", "invalid_turn", "timeout"]},
        "reason": _TEXT,
        "new_objections_this_round": {"type": "integer", "minimum": 0},
    },
}

SCHEMAS = {"proposer": PROPOSER, "critic_dx": CRITIC_DX, "critic_plan": CRITIC_PLAN, "stop": STOP}

_TYPES = {"object": dict, "array": list, "string": str, "boolean": bool}


def _is_type(value, name):
    if name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    return isinstance(value, _TYPES[name])


def validate(instance, schema, path="$"):
    """Return a list of error strings (empty list = valid)."""
    errors = []
    t = schema.get("type")
    if t and not _is_type(instance, t):
        return [f"{path}: expected {t}, got {type(instance).__name__}"]
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} not in {schema['enum']}")
    if isinstance(instance, str):
        if len(instance.strip()) < schema.get("minLength", 0):
            errors.append(f"{path}: text is empty")
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errors.append(f"{path}: {instance!r} does not match {schema['pattern']}")
    if t == "integer":
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: {instance} below minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(f"{path}: {instance} above maximum {schema['maximum']}")
    if isinstance(instance, dict):
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}: missing required field '{key}'")
        for key, val in instance.items():
            if key in props:
                errors += validate(val, props[key], f"{path}.{key}")
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}: unexpected field '{key}'")
    if isinstance(instance, list):
        if len(instance) < schema.get("minItems", 0):
            errors.append(f"{path}: needs at least {schema['minItems']} item(s)")
        if "items" in schema:
            for i, item in enumerate(instance):
                errors += validate(item, schema["items"], f"{path}[{i}]")
    return errors


def validate_turn(turn):
    """Validate one model turn (dict) by its 'role'. Return a list of error strings.

    The harness sends this text back to the model for the one allowed retry (SPEC section 2).
    """
    if not isinstance(turn, dict):
        return ["$: turn must be a JSON object"]
    role = turn.get("role")
    if role not in SCHEMAS:
        return [f"$.role: {role!r} is not one of {sorted(SCHEMAS)}"]
    return validate(turn, SCHEMAS[role])


def is_valid(turn):
    return not validate_turn(turn)
