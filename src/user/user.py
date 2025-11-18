import json
from datetime import timedelta
from flask import jsonify
from sqlalchemy import text, delete, update
from sqlalchemy.dialects.postgresql import insert
from src.config import MAIN_META
from src.consts import UserRoles
from src.user.utils import jsonb_set_stmt
from src.auth.misc import password_hash_json, invite_payload_json
from src.auth.jwt import create_access_token
from src.aliases import FieldAlias
from src.sql_utils import read_sql, execute_sql_and_commit
from src.utils import get_logger

logger = get_logger(__name__)


def get_users_list() -> list:
    """Возвращает список пользователей
    """
    df = read_sql("""SELECT id:: text, login, alias, role FROM skolkovo_general.users""")
    return json.loads(df.to_json(orient="records", force_ascii=False))


class User():
    layers_table = MAIN_META.tables['skolkovo_general.layers']
    users_table = MAIN_META.tables['skolkovo_general.users']

    def __init__(self, identity: str = None, role: UserRoles = UserRoles.VISITOR):
        self.identity = identity
        #TODO: роль должна браться из таблицы
        self.role = role

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
    def get_field_aliases(cls):
        """Возвращает список алиасов полей пользователя в формате Json

        Returns:
            dict: список алиасов пользователя
        """
        
        fields = FieldAlias()
        return fields.get_field_aliases()
    
    @classmethod
    def add(cls, payload: dict):
        val = { 
            'login': payload['login'].strip(),
            'alias': f"{payload['last_name']} {payload['first_name']} {payload['middle_name']}".strip(),
            'role': payload.get("role", UserRoles.VISITOR),
            'state': {
                "verified": invite_payload_json(),
                "password": password_hash_json(),
            }
        }        
        # upsert (on conflict do nothing/ update) — здесь создаём, при конфликте можно вернуть 409
        c = cls.users_table.c
        stmt = insert(cls.users_table).values(val).on_conflict_do_nothing().returning(c.id, c.login, c.alias, c.role, c.state)
        res = execute_sql_and_commit(stmt).fetchone()
        return {
            'id': str(res[0]), 
            'login': res[1],
            'alias': res[2],
            'role': res[3],
            'state': res[4],
        }
    

    def remove(self):
        q = delete(self.users_table).where(self.users_table.c.id == self.identity)
        res = execute_sql_and_commit(q)
        # res.rowcount может отсутствовать — проверим по факту
        #if not self.exists():
        #    return jsonify({"status": "bad", "error": "Failed to delete user"}), 500
        return jsonify({"status": "ok"}), 200
    

    def set_role(self, new_role: UserRoles):
        q = update(self.users_table).where(self.users_table.c.id == self.identity).values(role=new_role)
        execute_sql_and_commit(q)

        # Можно инвалидировать старые токены, если храните их в state -> access_token
        # Например просто удалить access_token:
        q = text(f"""
            UPDATE skolkovo_general.users
            SET state = {jsonb_set_stmt(["access_token"], "null")}
            WHERE id = :uid
        """)
        execute_sql_and_commit(q.bindparams(uid=self.identity))

        return jsonify({"status": "role_updated"}), 200
    

    def refresh_invitation_state(self, regenerate_password: bool = False):
        # Обновляем verified
        j_verified = invite_payload_json()
        q = text(f"""
            UPDATE skolkovo_general.users
            SET state = {jsonb_set_stmt(["verified"], j_verified)}
            WHERE id = :uid
        """)
        execute_sql_and_commit(q.bindparams(uid=self.identity))

        if regenerate_password:
            j_pwd = password_hash_json()
            q = text(f"""
                UPDATE skolkovo_general.users
                SET state = {jsonb_set_stmt(["password"], j_pwd)}
                WHERE id = :uid
            """)
            execute_sql_and_commit(q.bindparams(uid=self.identit))


    def exists(self, token: str = None) -> bool:
        """
        Проверяет существование пользователя с данным identity
        """

        token_check = f"and state ->> 'access_token' = {token}"
        df = read_sql(f"""
            SELECT 1 from skolkovo_general.users where id = '{self.identity}' {token_check if token else ''}
        """)
        return len(df) > 0


    def get_info(self) -> dict:
        """По userid из авторизации ЕСИА возвращает информацию о пользователе
        """
        df = read_sql("""
            SELECT login, alias, role, state::text
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