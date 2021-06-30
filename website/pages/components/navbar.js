import styles from '../../styles/Home.module.css'

export default function NavBar() {
    return (
        <nav className={styles.nav}>
            <a href="/tutorial">Tutorials</a>
            <a href="/docs">Docs</a>
        </nav>
    )
}

