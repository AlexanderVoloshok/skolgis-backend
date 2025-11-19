import json
from sqlalchemy.dialects.postgresql import insert
from src.config import MAIN_META
from src.sql_utils import read_sql, execute_sql_and_commit


class FieldAlias:
    alias_table = MAIN_META.tables['skolkovo_general.attr_alias']

    def __init__(self):
        pass


    def get_field_aliases(self, orient="records"):
        df = read_sql("""
            WITH user_cols as (
            	SELECT aa.attr_name, aa.alias FROM skolkovo_general.attr_alias aa
            )
            SELECT columns.column_name as attr_name, case 
            	when alias = '' or alias is null then columns.column_name
            	else alias
            end
            as alias, table_name FROM information_schema.columns
            left join user_cols on columns.column_name = user_cols.attr_name
            WHERE columns.table_name in (
            	select table_name FROM skolkovo_general.layers where layers_type_id !=3 
            ) and columns.column_name not in ('id', 'geom')
            order by attr_name;
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