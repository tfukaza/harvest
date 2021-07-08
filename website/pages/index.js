import NavBar from './components/navbar.js'
import Header from './components/header.js'
import Footer from './components/footer.js'
import Link from 'next/link'


import styles from '../styles/Home.module.scss'
import rc from '../styles/rowcrop.module.css'

export default function Home() {
  return (
    <div className={styles.container}>
      <Header title="Harvest - Algo trading framework for tinkers"></Header>
      <NavBar></NavBar>
      <main className={styles.main}>
        
        <section className={styles.section} id={styles.landing}>
          <h1 className={styles.title}>
            Algo-trading framework for <a href="https://www.merriam-webster.com/dictionary/tinker">tinkerers</a>
          </h1>
          <p>
            Harvest is a simple yet robust 
            Python framework for algorithmic trading.
          </p>
          <Link href="/tutorial/starter">
            <a className={`${rc.button} ${styles.button}`}>
              Startup Guide
            </a>
          </Link>
        </section>
        <section className={styles.section}>
          <div className={styles.col_card}>
            <img src="https://via.placeholder.com/512"></img>
            <h2>Beginners Welcome</h2>
            <p>
            If you’re new to trading, coding, or both - no worries, 
            Harvest was specifically designed so beginners in 
            both trading and coding can easily get started. 
            </p>
          </div>
          <div className={styles.col_card}>
            <img src="https://via.placeholder.com/512"></img>   
            <h2>Exotic Features</h2>
            <p>
            Harvest’s philosophy is that rather than 
            absolute stability, it’s better to support experimental, 
            exciting features while maintaining a practical level 
            of reliability. 
            </p>
          </div>
          <div className={styles.col_card}>
            <img src="https://via.placeholder.com/512"></img>
            <h2>Built to be Modded</h2>
            <p>
            The codebase is designed so developers can easily to add their 
            own code and implement custom features. 
            </p>
          </div>
        </section>
      </main>

      <Footer></Footer>
    </div>
  )
}
