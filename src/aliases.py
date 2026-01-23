import json
from sqlalchemy.dialects.postgresql import insert
from src.config import MAIN_META
from src.sql_utils import read_sql, execute_sql_and_commit

#TODO: одно и то же поле в разных слоях может называться по-разному
class FieldAlias:
    alias_table = MAIN_META.tables['skolkovo_general.attr_alias']

    def __init__(self, layer_name: str = None):
        self.layer_name = layer_name


    def get_field_aliases(self, orient="records"):
        df = read_sql("""
            SELECT * FROM skolkovo_general.field_aliases
        """)
        
        return df.set_index('attr_name')['alias'].to_dict() if orient=="dict" else json.loads(df.to_json(orient="records"))
    

    def save(self, fields: dict):
        queries = []
        for attr_name, alias in fields.items():
            stmt = insert(self.alias_table).values(
                attr_name=attr_name,
                alias=alias
            ).on_conflict_do_update(
                index_elements=['attr_name'],  # порядок должен совпадать с уникальным индексом
                set_={'alias': alias}
            )
            queries.append(stmt)
        cursor = execute_sql_and_commit(queries)
        return {"status": "ok", "fields": self.get_field_aliases()}