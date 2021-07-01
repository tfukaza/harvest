import Head from 'next/head'

export default function Header({c, title}) {
    return (
        <Head>
            <title>{title}</title>
            <meta name="description" content=""/>
            <link rel="icon" href="/favicon.ico" />
        </Head>
    )
}


