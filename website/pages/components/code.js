import rc from '../../styles/rowcrop.module.css'
import SyntaxHighlighter from 'react-syntax-highlighter';

export default function CodeBlock({lang, value}) {
    if (lang === undefined){ lang = "text"; }
    if (value === undefined) { value = "Hello World"; }
    return (
        <div className={rc.code}>
            <SyntaxHighlighter
                language={lang}>
                {value}
            </SyntaxHighlighter>
        </div>
    )
}