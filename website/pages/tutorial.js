import NavBar from './components/navbar.js'
import Header from './components/header.js'

import styles from '../styles/Home.module.css'
import rc from '../styles/rowcrop.module.css'

export default function Home() {
  return (
    <div className={styles.container}>
      <Header title="Harvest | Tutorials"></Header>
      <NavBar></NavBar>
      <main className={styles.main}>
        
      </main>

      <footer className={styles.footer}>
        
      </footer>
    </div>
  )
}
