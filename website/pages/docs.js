import NavBar from './components/navbar.js'
import Header from './components/header.js'
import Function from './components/func.js'
import Link from 'next/link'

import styles from '../styles/Home.module.css'
import doc from '../styles/Doc.module.css'
import rc from '../styles/rowcrop.module.css'

import algos from './docs-content/algo.json'

export default function Home() {
  let algo_items = [];
  let algo_func = [];
  for (let val of algos){
    algo_items.push(<Function dict={val}></Function>);
    algo_func.push(<Link 
                    href={'/docs#'+val["short"]}
                    passHref>
                      <li>{val["short"]}</li></Link>)
  }

  return (
    <div className={styles.container}>
      <Header title="Harvest | Documentation"></Header>
      <NavBar></NavBar>
      <section></section>
      
      <main className={styles.main}>
        
        <section className={styles.section}>
          <h1>Documentation</h1>
          <nav className={`${doc.nav} ${rc.card}`}>
          <h3>Algo</h3>
          <ul>
           {algo_func}
          </ul>
        </nav>
          {algo_items}
        </section>
      </main>

      <footer className={styles.footer}>
        
      </footer>
    </div>
  )
}
