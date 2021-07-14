import NavBar from './components/navbar.js'
import Header from './components/header.js'
import Footer from './components/footer.js'
import Function from './components/func.js'
import Link from 'next/link'

import styles from '../styles/Home.module.scss'
import doc from '../styles/Doc.module.css'
import rc from '../styles/rowcrop.module.css'

import algos from './docs-content/BaseAlgo.json'
import trader from './docs-content/Trader.json'
import backtester from './docs-content/BackTester.json'

export default function Home() {
  let algo_items = [];
  let algo_func = [];
  for (let val of algos){
    algo_items.push(<Function dict={val}></Function>);
    algo_func.push(<Link 
                    href={'/docs#'+val["index"]}
                    passHref>
                      <li>{val["index"]}</li></Link>)
  }

  return (
    <div className={styles.container}>
      <Header title="Harvest | Documentation"></Header>
      <NavBar></NavBar>      
      <main className={styles.main}>
          <nav className={`${doc.nav} ${rc.card}`}>
            <h3>Algo</h3>
            <ul>
            {algo_func}
            </ul>
          </nav>
        <section className={styles.section}>
          <h1>Documentation</h1>
          <h2 className={doc.className}>harvest.Algo</h2>
          {algo_items}
        </section>
      </main>

      <Footer></Footer>
    </div>
  )
}
