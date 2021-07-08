import styles from '../../styles/Home.module.scss'
import Link from 'next/link'

export default function Footer() {
    return (
        <footer className={styles.footer}>
            <section className={styles.section}>
            <div>
                <img src="/wordmark.svg"></img>
                <Link href="https://github.com/tfukaza/harvest/issues/new?assignees=&labels=bug&template=bug_report.md&title=%5B%F0%9F%AA%B0BUG%5D">Report a Bug</Link>
                <Link href="https://github.com/tfukaza/harvest/issues/new?assignees=&labels=enhancement%2C+question&template=feature-request.md&title=%5B%F0%9F%92%A1Feature+Request%5D">Suggest a Feature</Link>
            </div>
            <div>
                <h3>Special thanks to these projects:</h3>
                <Link href="https://github.com/jmfernandes/robin_stocks">robin_stocks</Link>
            </div>
            </section>
        </footer>
    )
}

