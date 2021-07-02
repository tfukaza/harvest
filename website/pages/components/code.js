import SyntaxHighlighter from 'react-syntax-highlighter';

export default function CodeBlock({lang, value}) {
    if (lang === undefined){ lang = "text"; }
    if (value === undefined) { value = "Hello World"; }
    return (
            <SyntaxHighlighter
                language={lang}
                customStyle={''}
                useInlineStyles={false}>
                {value}
            </SyntaxHighlighter>
    )
}