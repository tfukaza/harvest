import doc from '../../styles/Doc.module.css'
import CodeBlock from './code'
import dict from '../docs-content/def.json'

function get_def(word){
    if (word in dict){
        return dict[word];
    } else {
        return "404";
    }
}

export default function Function({dict}) {
    if (dict === undefined)
        return(<p>:)</p>);
    let params=[]
    // Parse through method parameters
    for (let v of dict["params"]){

        let desc_text = v["desc"];
        if (desc_text === undefined) desc_text = "";
    
        // Match any {} patterns
        let regex = /{[^{}]+}/g;
        let matches = desc_text.match(regex);
        let desc_split = desc_text.split(regex);

        let nodes = [];
        let word = '';
        let tooltip = null;
        for (let d of desc_split){
            nodes.push(d);
            if (matches !== null && matches.length > 0){
                word = matches.shift().replace(/[{}]/g, '');
                tooltip = <span>{get_def(word)}</span>;
                nodes.push(<span className={doc.lookup}>{tooltip}{word}</span>)
            }
        }

        params.push(
            <div>
                <p className={doc.paramName}>• {v["name"]}</p>
                <p className={doc.paramType}>&nbsp;({v["type"]}):</p>
                <p>{nodes}</p>
                <p className={doc.paramDef}>{v["default"]}</p>
                <p>{matches}</p>
            </div>
        );   
    }
    return (
            <div className={doc.entry} id={dict["index"]}>
            <CodeBlock
                lang="python"
                value={dict["function"]}>
            </CodeBlock>
            <p>{dict["short_description"]}</p>
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