const my_loader = (src) => {
    let base = process.env.BASE_PATH;
    if (base === undefined) base = '';
    return `{${base}/${src}}`
}

export default function StaticImage({props, src}) {
    if (src === undefined) return (<img />)
    return (
        <img src={my_loader(src)} alt="img" />
    )
}   