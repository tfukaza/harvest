import styles from '../../styles/Home.module.css'
import Link from 'next/link'

export default function NavBar() {
    return (
        <nav className={styles.nav}>
            <Link href="/tutorial"><a>Tutorials</a></Link>
            <Link href="/docs"><a>Docs</a></Link>
        </nav>
    )
}

