

def jsonb_set_stmt(field_path: list[str], value_json: str):
    """
    Возвращает SQL-фрагмент jsonb_set(state::jsonb, '{a,b}', '<json>', true).
    value_json должен быть валидным JSON (кавычки и т.п. уже расставлены).
    """
    path = "{" + ",".join(field_path) + "}"
    return f"jsonb_set(state::jsonb, '{path}', {value_json}, true)"