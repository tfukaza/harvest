import Head from 'next/head'

export default function Header({c, title}) {
    return (
        <Head>
            <title>{title}</title>
            <meta name="description" content=""/>
            <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
            <meta property="og:title" content={title}/>
            <meta property="og:type" content="website"/>
            <meta property="og:image" content="/wordmark.svg"/>
            <link rel="icon" href="/favicon.ico" />
        </Head>
    )
}


