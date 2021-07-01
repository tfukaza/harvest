import rc from '../../styles/rowcrop.module.css'

import { Light as SyntaxHighlighter } from 'react-syntax-highlighter';
import python from 'react-syntax-highlighter/dist/esm/languages/hljs/python';
import bash from 'react-syntax-highlighter/dist/esm/languages/hljs/bash';

SyntaxHighlighter.registerLanguage('python', python);
SyntaxHighlighter.registerLanguage('bash', bash);


export default function CodeBlock({lang, value}) {
    return (
        <div className={rc.code}>
            <SyntaxHighlighter
                language={lang}>
                {value}
            </SyntaxHighlighter>
        </div>
    )
}