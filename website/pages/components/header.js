import Head from 'next/head'
import StaticImage from './static_image'

export default function Header({c, title}) {
    let base = process.env.BASE_PATH;
    if (base === undefined) base = '';
    return (
        <Head>
            <title>{title}</title>
            <meta name="description" content=""/>
            <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
            <meta property="og:title" content={title}/>
            <meta property="og:type" content="website"/>
            <meta property="og:image" content="https://tfukaza.github.io/harvest/logo.png"/>
            <link rel="icon" href="/favicon.ico" />
        </Head>
    )
}


