import Image from 'next/image'

const my_loader = ({ src, }) => {
  return `{${process.env.BASE_PATH}/${src}}`
}

export default StaticImage = (props, src) => {
  return (
    <Image
      loader={my_loader}
      src={src}
      alt="Picture"
    />
  )
}