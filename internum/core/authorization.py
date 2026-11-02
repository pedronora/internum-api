from collections.abc import Iterable
from enum import Enum

from internum.modules.users.enums import Role


class Permission(str, Enum):
    USERS_CREATE = 'users:create'
    USERS_READ = 'users:read'
    USERS_READ_SENSITIVE = 'users:read_sensitive'
    USERS_EDIT_PROFILE = 'users:edit_profile'
    USERS_EDIT_EMPLOYMENT = 'users:edit_employment'
    USERS_EDIT_SALARY = 'users:edit_salary'
    USERS_ASSIGN_ROLES = 'users:assign_roles'
    LEGAL_BRIEFS_MANAGE = 'legal_briefs:manage'
    NOTICES_MANAGE = 'notices:manage'
    LIBRARY_MANAGE = 'library:manage'
    VACATION_READ_ALL = 'vacation:read_all'
    VACATION_MANAGE_ALL = 'vacation:manage_all'
    VACATION_CONFIRM_FRUITION = 'vacation:confirm_fruition'


ALL_PERMISSIONS = frozenset(Permission)

_COLLABORATOR_PERMISSIONS = frozenset({Permission.USERS_READ})

_COORDENACAO_PERMISSIONS = frozenset({
    Permission.USERS_CREATE,
    Permission.USERS_READ,
    Permission.USERS_READ_SENSITIVE,
    Permission.USERS_EDIT_PROFILE,
    Permission.USERS_EDIT_EMPLOYMENT,
    Permission.USERS_ASSIGN_ROLES,
    Permission.NOTICES_MANAGE,
    Permission.LIBRARY_MANAGE,
    Permission.VACATION_READ_ALL,
    Permission.VACATION_MANAGE_ALL,
    Permission.VACATION_CONFIRM_FRUITION,
})

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ADMIN: ALL_PERMISSIONS,
    Role.OFICIAL: ALL_PERMISSIONS,
    Role.SUBOFICIAL: ALL_PERMISSIONS,
    Role.COORD_REGISTRO: _COORDENACAO_PERMISSIONS
    | {Permission.LEGAL_BRIEFS_MANAGE},
    Role.COORD_GESTAO: _COORDENACAO_PERMISSIONS,
    Role.GESTOR_PESSOAS: _COORDENACAO_PERMISSIONS
    | {Permission.USERS_EDIT_SALARY},
    Role.COLABORADOR_REGISTRO: _COLLABORATOR_PERMISSIONS,
    Role.COLABORADOR_GESTAO: _COLLABORATOR_PERMISSIONS,
}

_ASSIGNABLE_ROLES: dict[Role, frozenset[Role]] = {
    Role.ADMIN: frozenset(Role),
    Role.OFICIAL: frozenset(Role) - {Role.ADMIN},
    Role.SUBOFICIAL: frozenset(Role) - {Role.ADMIN},
    Role.GESTOR_PESSOAS: frozenset({
        Role.COLABORADOR_REGISTRO,
        Role.COLABORADOR_GESTAO,
    }),
    Role.COORD_GESTAO: frozenset({Role.COLABORADOR_GESTAO}),
    Role.COORD_REGISTRO: frozenset({Role.COLABORADOR_REGISTRO}),
}


def permissions_for_roles(roles: Iterable[Role]) -> frozenset[Permission]:
    permissions: set[Permission] = set()
    for role in roles:
        permissions.update(ROLE_PERMISSIONS.get(role, frozenset()))
    return frozenset(permissions)


def has_permission(roles: Iterable[Role], permission: Permission) -> bool:
    return permission in permissions_for_roles(roles)


def is_admin(roles: Iterable[Role]) -> bool:
    return Role.ADMIN in roles


def assignable_roles(actor_roles: Iterable[Role]) -> frozenset[Role]:
    allowed: set[Role] = set()
    for role in actor_roles:
        allowed.update(_ASSIGNABLE_ROLES.get(role, frozenset()))
    return frozenset(allowed)


def can_assign_role(actor_roles: Iterable[Role], role: Role) -> bool:
    return role in assignable_roles(actor_roles)
