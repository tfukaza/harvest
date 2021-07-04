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

function generate_params(dict){
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
    return params;
}

function generate_raises(dict){
    let raises=[];
    for (let v of dict["raises"]){
        raises.push(
            <li><span>{v["type"]+': '}</span>{v["desc"]}</li>
        );   
    }
    return raises;
}

function generate_returns(dict){
    let nodes=[];
    let text = dict["returns"]; 

    // Find all lists in the text
    let lists = text.match(/(\s*\n\s*- .+)+/g);
    let texts = text.split(/\s*- [^\n]*/).filter(s => s.length > 0);

    for (let t of texts){
        nodes.push(<p>{t}</p>);
        if (lists !== null && lists.length > 0){
            let list = lists.shift();
            let lines = list.match(/-.*[^\n]/g);
            let line_nodes = [];
            for (let l of lines){
                line_nodes.push(<li>{l.replace(/- /, '')}</li>);
            }
            nodes.push(<ul>{line_nodes}</ul>); 
        }
    }

    return nodes;
}

<p>{dict["returns"]}</p>

export default function Function({dict}) {
    if (dict === undefined)
        return(<p>:)</p>);

    let params = generate_params(dict);
    let raises = generate_raises(dict);
    let returns = generate_returns(dict);
    return (
            <div className={doc.entry} id={dict["index"]}>
            <CodeBlock
                lang="python"
                value={dict["function"]}>
            </CodeBlock>
            <p>{dict["short_description"]}</p>
            <p className={doc.longDesc}>{dict["long_description"]}</p>
            <div className={doc.paramHeader}>
                <h3>Params:</h3><h4>Default</h4>
                {params}
            </div>
            <div className={doc.paramReturn}>
                <h3>Returns:</h3>{returns}</div>
            <div className={doc.paramRaise}>
                <h3>Raises:</h3>
                <ul className={doc.raises}>{raises}</ul></div>
          
            </div>
    )
}