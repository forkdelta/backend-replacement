# backend-replacement

Best way to learn about a system is to read the source code. Start with a look at [docker-compose.yml](docker-compose.yml).

Requirements:
* Some sort of shell environment
* A reasonably recent version of Docker (>= 17.06, ideally 17.12)
* docker-compose (= 1.18)
* Basic familiarity with Docker keywords: image, container (https://docs.docker.com/get-started/#docker-concepts)

Setup:
1. Clone the repo (git clone https://github.com/forkdelta/backend-replacement.git)
2. Navigate to the root of the working copy, where the README file is.
3. Rename/copy `default.env` file to `.env` in root
4. Build a Docker image containing our backend code: `docker-compose build contract_observer`
5. Create the database and migrate it to the latest schema: `docker-compose run contract_observer alembic upgrade head`
6. Run the backend systems: `docker-compose up`. You can shut everything down with Ctrl+C at any time.

Tips:
* There are multiple containers running our backend code: contract_observer, etherdelta_observer, websocket_server
* Running docker-compose build <service-name> for any of the above builds the same image.
* docker-compose build contract_observer builds an image, copying the code and installing Python libraries in our dependencies.
  You have to rebuild any time the dependencies change; however, in development, code in the working copy is mounted into the container,
  so it's enough to restart the container (with docker-compose restart <service-name>) to apply changes for a given service.
* You can inspect the list of currently running containers with docker-compose ps
