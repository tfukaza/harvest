import styles from '../../styles/Home.module.css'
import Link from 'next/link'

export default function NavBar() {
    return (
        <nav className={styles.nav}>
            <div>
            <Link href="/tutorial"><a>Tutorials</a></Link>
            <Link href="/docs"><a>Docs</a></Link>
            </div>
            <Link href="https://github.com/tfukaza/harvest">GitHub</Link>
        </nav>
    )
}

