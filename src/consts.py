import enum

RESERVED_WORDS = {
    'all', 'analyse', 'analyze', 'and', 'any', 'array', 'as', 'asc', 'asymmetric',
    'authorization', 'between', 'binary', 'both', 'case', 'cast', 'check', 'collate',
    'collation', 'column', 'concurrently', 'constraint', 'create', 'cross', 'current_catalog',
    'current_date', 'current_role', 'current_schema', 'current_time', 'current_timestamp',
    'current_user', 'default', 'deferrable', 'desc', 'distinct', 'do', 'else', 'end', 'except',
    'false', 'fetch', 'for', 'foreign', 'from', 'full', 'grant', 'group', 'having', 'ilike',
    'in', 'initially', 'inner', 'intersect', 'into', 'is', 'isnull', 'id', 'join', 'lateral', 'leading',
    'left', 'like', 'limit', 'localtime', 'localtimestamp', 'natural', 'not', 'notnull', 'null',
    'offset', 'on', 'only', 'or', 'order', 'outer', 'overlaps', 'placing', 'primary', 'references',
    'returning', 'right', 'select', 'session_user', 'similar', 'some', 'symmetric', 'table',
    'then', 'to', 'trailing', 'true', 'union', 'unique', 'user', 'using', 'variadic', 'verbose',
    'when', 'where', 'window', 'with'
}

PROTECTED_COLUMN_NAMES_PROJECTS = ('project_id', 'name', 'func_purpose', 'parcel_area_ga', 'floors', 'spp_gab', 'stage', 'investor', 'year_entered', 'addings')
PROTECTED_COLUMN_NAMES_PARCELS = ('func_purpose', 'status')

class UserRoles(enum.Enum):
    VISITOR = "visitor"
    EDITOR = "editor"
    ADMIN = "admin"