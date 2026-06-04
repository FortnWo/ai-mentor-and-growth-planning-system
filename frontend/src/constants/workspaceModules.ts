export type WorkspaceModuleId = 'chat' | 'profile' | 'plan' | 'growth' | 'info'

export interface WorkspaceModule {
  id: WorkspaceModuleId
  path: string
  kicker: string
  title: string
  subtitle: string
  navLabel: string
}

export const STUDENT_WORKSPACE_MODULES: WorkspaceModule[] = [
  {
    id: 'chat',
    path: '/chat',
    kicker: 'AI 导师',
    title: '对话工作台',
    subtitle: '整理会话、对照上下文，让对话流保持安静而清晰。',
    navLabel: '聊天',
  },
  {
    id: 'profile',
    path: '/profile',
    kicker: '结构化画像',
    title: '用户画像实验室',
    subtitle: '通过手动编辑与聊天抽取，持续整理兴趣、技能、习惯和目标。',
    navLabel: '用户画像',
  },
  {
    id: 'plan',
    path: '/plan',
    kicker: '成长规划',
    title: '成长路线图',
    subtitle: '面向未来的规划入口，带着更清晰的目标感与成长信号。',
    navLabel: '目标计划',
  },
  {
    id: 'growth',
    path: '/growth',
    kicker: '成长记录',
    title: '成长记录工作台',
    subtitle: '记录每一个小进步，回看成长轨迹，让成长痕迹始终可见。',
    navLabel: '成长记录',
  },
  {
    id: 'info',
    path: '/info',
    kicker: '个人工作区',
    title: '身份信息工作台',
    subtitle: '查看你的身份概览，让资料保持干净、聚焦、及时更新。',
    navLabel: '我的资料',
  },
]

export function getWorkspaceModule(id: WorkspaceModuleId): WorkspaceModule | undefined {
  return STUDENT_WORKSPACE_MODULES.find((m) => m.id === id)
}
