const my_loader = ({ src, }) => {
  return `{${process.env.BASE_PATH}/${src}}`
}

export default function StaticImage({props, src}) {
    if (src === undefined) return (<img />)
    return (
        <img src={my_loader(src)} alt="img" />
    )
}   