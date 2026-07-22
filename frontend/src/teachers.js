import {
  CalculatorOutline,
  BookOutline,
  LanguageOutline,
  PlanetOutline,
  FlaskOutline,
  GlobeOutline,
  LibraryOutline,
  LeafOutline,
  ScaleOutline
} from '@vicons/ionicons5'

// 名师·技能预设（9 学科）。图标来自 @vicons，不使用任何 emoji。
export const TEACHERS = [
  {
    name: '数学名师',
    subject: '数学',
    icon: CalculatorOutline,
    color1: '#fef3c7',
    color2: '#fcd34d',
    tags: ['代数', '几何', '函数'],
    desc: '覆盖初高中数学全模块，精讲解题思路与技巧，帮你建立数学思维体系。',
    skills: ['方程求解', '函数图像', '几何证明', '数列求和'],
    prompt: '老师好，我有一道数学题不会做，请帮我讲解'
  },
  {
    name: '语文名师',
    subject: '语文',
    icon: BookOutline,
    color1: '#dcfce7',
    color2: '#86efac',
    tags: ['阅读', '写作', '古诗词'],
    desc: '从阅读理解到作文技巧，古诗词鉴赏到文言文翻译，全面提升语文素养。',
    skills: ['阅读理解', '作文指导', '古诗文鉴赏', '病句修改'],
    prompt: '老师好，请帮我分析这篇课文的写作手法'
  },
  {
    name: '英语名师',
    subject: '英语',
    icon: LanguageOutline,
    color1: '#dbeafe',
    color2: '#93c5fd',
    tags: ['语法', '词汇', '口语'],
    desc: '系统讲解语法规则、词汇记忆法、长难句分析，提升听说读写综合能力。',
    skills: ['语法精讲', '词汇拓展', '听力训练', '写作润色'],
    prompt: '老师好，我想练习英语口语对话'
  },
  {
    name: '物理名师',
    subject: '物理',
    icon: PlanetOutline,
    color1: '#fce7f3',
    color2: '#f9a8d4',
    tags: ['力学', '电磁学', '光学'],
    desc: '用生活化案例解释物理定律，实验演示加公式推导，让物理不再抽象。',
    skills: ['力学分析', '电路计算', '光学作图', '实验设计'],
    prompt: '老师好，请用生活中的例子给我解释牛顿第二定律'
  },
  {
    name: '化学名师',
    subject: '化学',
    icon: FlaskOutline,
    color1: '#e0e7ff',
    color2: '#a5b4fc',
    tags: ['有机', '无机', '实验'],
    desc: '元素周期表、化学反应方程式、实验操作规范，构建完整化学知识网络。',
    skills: ['方程式配平', '有机推断', '实验安全', '计算技巧'],
    prompt: '老师好，请帮我复习金属活动性顺序表'
  },
  {
    name: '地理名师',
    subject: '地理',
    icon: GlobeOutline,
    color1: '#d1fae5',
    color2: '#6ee7b7',
    tags: ['自然地理', '人文地理', '区域地理'],
    desc: '从气候地貌到人口城市，地图判读加案例分析，培养空间思维与区域认知。',
    skills: ['等高线判读', '气候类型', '工业区位', '环境保护'],
    prompt: '老师好，请帮我分析中国的季风气候特点'
  },
  {
    name: '历史名师',
    subject: '历史',
    icon: LibraryOutline,
    color1: '#fef9c3',
    color2: '#facc15',
    tags: ['中国史', '世界史', '史料分析'],
    desc: '时间轴梳理重大事件，多角度解读历史人物，培养唯物史观与批判思维。',
    skills: ['时间轴梳理', '史料辨析', '事件评述', '对比分析'],
    prompt: '老师好，请帮我梳理唐朝的兴衰历程'
  },
  {
    name: '生物名师',
    subject: '生物',
    icon: LeafOutline,
    color1: '#fce4ec',
    color2: '#f48fb1',
    tags: ['细胞', '遗传', '生态'],
    desc: '从细胞结构到生态系统，图解生命过程，让生物学变得直观有趣。',
    skills: ['有丝分裂', '遗传规律', '生态循环', '实验观察'],
    prompt: '老师好，请帮我画一张有丝分裂的过程图'
  },
  {
    name: '政治名师',
    subject: '政治',
    icon: ScaleOutline,
    color1: '#ede9fe',
    color2: '#c084fc',
    tags: ['经济', '政治', '哲学'],
    desc: '经济学原理、哲学思辨、法治观念，结合时事热点培养公民意识与思辨能力。',
    skills: ['经济原理', '哲学辨析', '法律常识', '时事评论'],
    prompt: '老师好，请帮我理解矛盾的普遍性与特殊性'
  }
]

export function findTeacher(subject) {
  return TEACHERS.find((t) => t.subject === subject) || null
}
