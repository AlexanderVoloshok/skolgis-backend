import json
from datetime import timedelta
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from config import MAIN_META
from consts import UserRoles
from auth.jwt import create_access_token
from sql_utils import read_sql, execute_sql_and_commit
from utils import get_logger

logger = get_logger(__name__)


class User():
    layers_table = MAIN_META.tables['skolkovo_general.layers']
    users_table = MAIN_META.tables['skolkovo_general.users']

    def __init__(self, identity: str = None):
        self.identity = identity
        self.role = UserRoles.VISITOR

    @classmethod
    def get_layers(cls):
        """Выдаёт список слоёв пользователя в формате Json

        Returns:
            dict: список слоёв пользователя
        """
        
        df = read_sql("""
            SELECT id, source, table_name, alias, layers_type_id, geom_type, style_json, is_on
            FROM skolkovo_general.layers WHERE layers_type_id in (1,3)
        """)
        return df.to_json(orient="records")
    
    @classmethod
    def add(cls, payload: dict):
        val = {
            'id': payload['id'], 
            'login': payload['email'],
            'alias': f"{payload['last_name']} {payload['first_name']} {payload['middle_name']}",
            'role': UserRoles.VISITOR,
            'state': {}
        }
        stmt = insert(cls.users_table).values(val).on_conflict_do_nothing()
        res = execute_sql_and_commit(stmt)

        company = payload['company']['title_short'].replace('"', '').replace("'", '')
        q2 = text("""
            update skolkovo_general.users set state=jsonb_set(state::jsonb,'{"company"}', '"%s"', true) where id = '%s'
        """ % (company, val['id']))
        res = execute_sql_and_commit(q2)

        return payload['id']
    

    def remove(self):
        return NotImplementedError()
    

    def set_role(self):
        return NotImplementedError()
    

    def exists(self, token: str):
        """
        Проверяет существование пользователя с данным identity
        """

        df = read_sql("""
            SELECT 1 from skolkovo_general.users where id = %s and state ->> 'access_token' = %s
        """, params=(self.identity, token))
        return len(df) > 0


    def get_info(self):
        """По userid из авторизации ЕСИА возвращает информацию о пользователе
        """
        df = read_sql("""
            SELECT login, alias, role, state ->> 'company' as company 
            FROM skolkovo_general.users WHERE id = %s""", params=(self.identity, ))
        if len(df) == 0:
            return {}
        return json.loads(df.to_json(orient="records", force_ascii=False))[0]
    

    def generate_auth_token(self):
        """Создаёт и сохраняет в БД новый acess_token для пользователя

        Returns:
            string: новый токен
        """
        expires = timedelta(7*3600*24) #7 суток
        new_token = create_access_token(identity=self.identity, role=self.role, expires_delta=expires)
        stmt = text("""
            update skolkovo_general.users set state=jsonb_set(state::jsonb,'{"access_token"}', '"%s"', true) where id = '%s'
        """ % (new_token, self.identity))
        execute_sql_and_commit(stmt)

        return new_token