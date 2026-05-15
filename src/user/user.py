import json
import secrets
from datetime import datetime, timezone
from flask import jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy import text, select, delete, update
from sqlalchemy.dialects.postgresql import insert
from src.config import MAIN_META
from src.consts import UserRoles
from src.user.utils import jsonb_set_stmt
from src.auth.misc import invite_payload_json
from src.auth.jwt import create_access_token
from src.aliases import FieldAlias
from src.sql_utils import read_sql, execute_sql_and_commit, execute_sql_query
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

    def __init__(self, identity: str = None):
        self.identity = identity
        info = self.get_info()
        self.role: UserRoles =  info['role'] if 'role' in info.keys() else UserRoles.VISITOR

    def get_layers(self):
        """Выдаёт список слоёв пользователя в формате Json

        Returns:
            dict: список слоёв пользователя
        """
        layers_type_id = '(1,3)' if self.role == UserRoles.VISITOR.value else '(1,2,3)'
        df = read_sql(f"""
            SELECT id, source, table_name, alias, layers_type_id, geom_type, style_json, is_on, has3D, ext_params
            FROM skolkovo_general.layers WHERE layers_type_id in {layers_type_id}
            ORDER BY id
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
    def authenticate(cls, email: str, password: str):
        cols = cls.users_table.c
        q = select(cols.id, cols.password_hash).where(cols.login == email.strip().lower())
        user = execute_sql_query(q).fetchone()
        if not user:
            return None
        if not user[1]:
            return None
        if not check_password_hash(str(user[1]), password):
            return None

        return cls(identity=str(user[0]))

    @classmethod
    def add(cls, payload: dict):
        val = { 
            'login': payload['login'].strip(),
            'alias': f"{payload['last_name']} {payload['first_name']} {payload['middle_name']}".strip(),
            'role': payload.get("role", UserRoles.VISITOR),
            'state': {
                "verified": invite_payload_json(),
                "invite_token": secrets.token_urlsafe(32),
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
    
    @classmethod
    def set_password(cls, token_hash: str, new_password: str):
        new_hash = generate_password_hash(new_password)

        q = text(f"""
            SELECT id, state, password_hash FROM skolkovo_general.users
            where state ->> 'invite_token' = '%s'
        """ % token_hash)
        user = execute_sql_query(q).fetchone()

        now = datetime.now(timezone.utc)

        try:
            state = json.loads(user[1]['verified'])
        except:
            state = user[1]['verified']
        if user[2] is not None:
            return jsonify({'message': 'Ссылка уже использована'}), 400

        if state['inv_expires_at'] is None or datetime.fromisoformat(state['inv_expires_at']) < now:
            return jsonify({'message': 'Срок действия ссылки истёк'}), 400

        q = text(f"""
            UPDATE skolkovo_general.users
            SET password_hash = '{new_hash}'
            WHERE id = :uid
        """)
        execute_sql_and_commit(q.bindparams(uid=user[0]))
        return jsonify({"status": "password updated"}), 200
    

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
        self.role = new_role
        return jsonify({"status": "role updated"}), 200
    

    def refresh_invitation_state(self):
        # Обновляем verified
        j_verified = invite_payload_json()
        q = text(f"""
            UPDATE skolkovo_general.users
            SET state = {jsonb_set_stmt(["verified"], j_verified)}
            WHERE id = :uid
        """)
        execute_sql_and_commit(q.bindparams(uid=self.identity))

        q = text("""
            UPDATE skolkovo_general.users
            SET state = jsonb_set(
                state::jsonb,
                '{invite_token}',
                to_jsonb('%s'::text),
                true
            )
            WHERE id = '%s';
        """ % (secrets.token_urlsafe(32), self.identity))
        execute_sql_and_commit(q)

    #TODO: проверка пользователя без self. по токену или паролю с логином
    def exists(self, token: str = None) -> bool:
        """
        Проверяет существование пользователя с данным identity
        """

        token_check = f"and state ->> 'access_token' = '{token}'"
        df = read_sql(f"""
            SELECT 1 from skolkovo_general.users where id = '{self.identity}' {token_check if token else ''}
        """)
        return len(df) > 0


    def get_info(self) -> dict:
        """По userid возвращает информацию о пользователе
        """

        df = read_sql("""
            SELECT login, alias, role, state::text
            FROM skolkovo_general.users WHERE id = :id""", params={"id": self.identity})
        
        if len(df) == 0:
            return {}
        return json.loads(df.to_json(orient="records", force_ascii=False))[0]
    

    def generate_auth_token(self):
        """Создаёт и сохраняет в БД новый acess_token для пользователя

        Returns:
            string: новый токен
        """
        new_token = create_access_token(identity=self.identity, role=self.role)
        stmt = text("""
            update skolkovo_general.users
            set state=jsonb_set(coalesce(state::jsonb, '{}'::jsonb),'{"access_token"}', '"%s"', true)
            where id = '%s'
        """ % (new_token, self.identity))
        execute_sql_and_commit(stmt)

        return new_token