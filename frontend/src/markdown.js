import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import katex from 'katex'

const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
  highlight(str, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        const out = hljs.highlight(str, { language: lang, ignoreIllegals: true }).value
        return `<pre class="hljs"><code>${out}</code></pre>`
      } catch (e) {
        /* ignore */
      }
    }
    return `<pre class="hljs"><code>${md.utils.escapeHtml(str)}</code></pre>`
  }
})

// 先抽取数学公式渲染为 KaTeX，用占位符保护，避免被 markdown 转义破坏
let _mathStore = []
function _stash(html) {
  _mathStore.push(html)
  return `MATH${_mathStore.length - 1}`
}

// 渲染单个公式；任何异常都降级为原始文本，绝不让整条消息白屏
function _renderMath(tex, displayMode) {
  try {
    return katex.renderToString(tex, { displayMode, throwOnError: false })
  } catch (e) {
    const esc = tex
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
    return `<code class="md-math-fallback">${displayMode ? '$$' : '$'}${esc}${displayMode ? '$$' : '$'}</code>`
  }
}

export function renderMarkdown(src) {
  _mathStore = []
  let text = src || ''
  text = text.replace(/\$\$([\s\S]+?)\$\$/g, (_m, tex) => _stash(_renderMath(tex, true)))
  text = text.replace(/\$([^\$\n]+?)\$/g, (_m, tex) => _stash(_renderMath(tex, false)))
  let html = md.render(text)
  html = html.replace(/MATH(\d+)/g, (_m, i) => _mathStore[+i] || '')
  return html
}
