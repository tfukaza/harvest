import NavBar from '../components/navbar.js'
import Header from '../components/header.js'
import Link from 'next/link'

import styles from './../../styles/Home.module.css'
import rc from './../../styles/rowcrop.module.css'

export default function Home() {
  return (
    <div className={styles.container}>
      <Header title="Harvest | Tutorials"></Header>
      <NavBar></NavBar>
      <main className={styles.main}>
        <section></section>

        
        <section className={styles.section}>
          <Link href="/tutorial/starter" passHref>
          <div className={`${rc.card} ${rc.col4} ${styles.col4}`}>
            <h2>Startup Guide</h2>
            <p>First time? No worries. This module will 
              get you algo-trading in no time. </p>
          </div>
          </Link>
          <div className={`${rc.card} ${rc.col4} ${styles.col4}`}>
            <h2>Traders</h2>
              <p>Coming Soon</p>
          </div>
          <div className={`${rc.card} ${rc.col4} ${styles.col4}`}>
            <h2>Assets</h2>
            <p>Coming Soon</p>
          </div>
          <div className={`${rc.card} ${rc.col4} ${styles.col4}`}>
            <h2>Testing</h2>
            <p>Coming Soon</p>
          </div>
        </section>
      </main>

      <footer className={styles.footer}>
        
      </footer>
    </div>
  )
}
