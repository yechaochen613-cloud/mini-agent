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
  return `MATH${_mathStore.length - 1}`
}

export function renderMarkdown(src) {
  _mathStore = []
  let text = src || ''
  text = text.replace(/\$\$([\s\S]+?)\$\$/g, (_m, tex) =>
    _stash(katex.renderToString(tex, { displayMode: true, throwOnError: false }))
  )
  text = text.replace(/\$([^\$\n]+?)\$/g, (_m, tex) =>
    _stash(katex.renderToString(tex, { displayMode: false, throwOnError: false }))
  )
  let html = md.render(text)
  html = html.replace(/MATH(\d+)/g, (_m, i) => _mathStore[+i] || '')
  return html
}
