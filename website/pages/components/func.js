import doc from '../../styles/Doc.module.css'
import CodeBlock from './code'

export default function Function({dict}) {
    let params=[]
    for (let v of dict["params"]){
        params.push(
            <div>
                <p className={doc.paramName}>• {v["name"]}</p>
                <p className={doc.paramType}>&nbsp;({v["type"]}):</p>
                <p className={doc.paramDesc}>&nbsp;{v["description"]}</p>
                <p className={doc.paramDef}>{v["default"]}</p>
            </div>
        );   
    }
    return (
            <div className={doc.entry} id={dict["short"]}>
            <CodeBlock
                lang="python"
                value={dict["name"]}>
            </CodeBlock>
            <p>{dict["description"]}</p>
            <div className={doc.paramHeader}>
                <h3>Params:</h3><h4>Default</h4>
                {params}
            </div>
            <div className={doc.paramReturn}>
                <h3>Returns:</h3><p>{dict["returns"]}</p></div>
            <div className={doc.paramRaise}>
                <h3>Raises:</h3>
                <p>{dict["raises"]}</p></div>
          
            </div>
    )
}