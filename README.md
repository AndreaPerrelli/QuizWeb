# Quiz App

## Descrizione
Quiz App è un'applicazione web interattiva per la creazione, la condivisione e la partecipazione a quiz. Sviluppata con Flask, questa applicazione offre un'interfaccia user-friendly per gestire quiz su vari argomenti.

## Caratteristiche Principali
- Registrazione e autenticazione degli utenti
- Creazione e modifica di quiz personalizzati
- Condivisione dei quiz con altri utenti
- Partecipazione ai quiz con domande e risposte mescolate
- Visualizzazione dei risultati e delle statistiche

## Requisiti
- Python 3.7+
- Flask
- SQLite3
- Altre dipendenze elencate in `requirements.txt`

## Installazione
1. Clona il repository:
   ```
   git clone https://github.com/AndreaPerrelli/QuizWeb
   cd quiz-app
   ```

2. Crea un ambiente virtuale e attivalo:
   ```
   python -m venv venv
   source venv/bin/activate  # Su Windows usa `venv\Scripts\activate`
   ```

3. Installa le dipendenze:
   ```
   pip install -r requirements.txt
   ```

4. Configura le variabili d'ambiente:
   Crea un file `.env` nella directory principale e aggiungi:
   ```
   SECRET_KEY=la_tua_chiave_segreta
   EMAIL_USER=il_tuo_indirizzo_email
   EMAIL_PASSWORD=la_tua_password_email
   ```

5. Inizializza il database:
   ```
   python app.py
   ```

## Utilizzo
1. Avvia l'applicazione:
   ```
   python app.py
   ```

2. Apri un browser e vai all'indirizzo `http://localhost:5000`

3. Registrati o accedi per iniziare a creare o partecipare ai quiz

## Struttura del Progetto
- `app.py`: File principale dell'applicazione Flask
- `templates/`: Contiene tutti i template HTML
- `static/`: File statici (CSS, JavaScript, immagini)
- `database.db`: Database SQLite

## Contribuire
Siamo aperti a contributi! Se desideri contribuire al progetto, segui questi passaggi:
1. Fai un fork del repository
2. Crea un nuovo branch (`git checkout -b feature/AmazingFeature`)
3. Committa le tue modifiche (`git commit -m 'Add some AmazingFeature'`)
4. Pusha il branch (`git push origin feature/AmazingFeature`)
5. Apri una Pull Request

## Licenza
Distribuito sotto la licenza Apache-2.0 license. Vedi `LICENSE` per maggiori informazioni.

## Contatti
Andrea Antonio Perrelli - [LinkedIn](https://www.linkedin.com/in/andrea-antonio-perrelli-3b429b17b/) - email@example.com

Link del Progetto: [GitHub](https://github.com/AndreaPerrelli/QuizWeb)