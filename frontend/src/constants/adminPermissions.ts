export type AdminPermissionKey =
  | 'user.read'
  | 'user.create'
  | 'user.update'
  | 'user.delete'
  | 'admin.grant'

export type AdminPermissionOption = {
  key: AdminPermissionKey
  label: string
  description: string
}

/** Matches require_admin(...) keys in backend/app/routers/user.py */
export const ADMIN_PERMISSION_OPTIONS: AdminPermissionOption[] = [
  {
    key: 'user.read',
    label: '查看用户',
    description: '列出与查看用户详情',
  },
  {
    key: 'user.create',
    label: '创建用户',
    description: '创建新账号',
  },
  {
    key: 'user.update',
    label: '更新用户',
    description: '修改资料、启用/禁用等',
  },
  {
    key: 'user.delete',
    label: '删除用户',
    description: '删除用户账号',
  },
  {
    key: 'admin.grant',
    label: '管理员授权',
    description: '授予或撤销管理员权限',
  },
]

export const ADMIN_PERMISSION_KEYS = ADMIN_PERMISSION_OPTIONS.map((option) => option.key)

/** Default permissions granted by the one-click admin grant button. */
export const DEFAULT_ONE_CLICK_ADMIN_PERMISSIONS: AdminPermissionKey[] = [
  'user.read',
  'user.create',
  'user.update',
]
