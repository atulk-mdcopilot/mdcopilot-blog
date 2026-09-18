import CodeMirror, { EditorView } from '@uiw/react-codemirror'
import { markdown } from '@codemirror/lang-markdown'
const extensions = [
  markdown(),
  EditorView.lineWrapping,
  EditorView.contentAttributes.of({ 'aria-label': 'Article Markdown' }),
]
export function MarkdownEditor({
  value,
  onChange,
  readOnly,
}: {
  value: string
  onChange: (value: string) => void
  readOnly: boolean
}) {
  return (
    <CodeMirror
      value={value}
      extensions={extensions}
      onChange={onChange}
      readOnly={readOnly}
      minHeight="440px"
      maxHeight="70vh"
      className="overflow-hidden rounded-md border text-sm"
    />
  )
}
