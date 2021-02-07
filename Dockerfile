# Setup solver
FROM ubuntu:xenial

RUN apt-get update
RUN apt-get -y install --no-install-recommends git subversion gcc g++ make wget gfortran patch pkg-config file
RUN apt-get -y install --no-install-recommends libgfortran-5-dev libblas-dev liblapack-dev libmetis-dev libnauty2-dev
RUN apt-get -y install --no-install-recommends ca-certificates

RUN git clone https://github.com/coin-or/coinbrew /var/coin-or
WORKDIR /var/coin-or
RUN ./coinbrew fetch COIN-OR-OptimizationSuite@stable/1.9 --skip="ThirdParty/Blas ThirdParty/Lapack ThirdParty/Metis" --no-prompt
RUN ./coinbrew build  COIN-OR-OptimizationSuite --skip="ThirdParty/Blas ThirdParty/Lapack ThirdParty/Metis" --no-prompt --prefix=/usr

# Setup python
RUN apt-get -y install software-properties-common
RUN add-apt-repository -y ppa:deadsnakes/ppa
RUN apt-get update
RUN apt-get -y install python3.9
RUN apt-get -y install python3.9-distutils
RUN apt-get -y install curl
RUN curl "https://bootstrap.pypa.io/get-pip.py" -o "get-pip.py"
RUN python3.9 get-pip.py

# Setup git
RUN apt-get install git
RUN apt-get -y install python3.9-dev

# Setup MySQL server
RUN echo 'mysql-server mysql-server/root_password password your_password' | debconf-set-selections
RUN echo 'mysql-server mysql-server/root_password_again password your_password' | debconf-set-selections
RUN apt-get -y install mysql-server
RUN apt-get -y install libmysqlclient-dev
RUN apt-get -y install libssl-dev

# Setup repo
RUN mkdir /app
COPY ./requirements.txt /app/
RUN python3.9 -m pip install -r /app/requirements.txt
COPY . /app
WORKDIR /app

EXPOSE 3306
CMD tail -f /dev/null

# COPY ./requirements.txt /requirements.txt

# # Create directory for scripts
# RUN mkdir /app
# RUN mkdir /app/scripts
# ENV PATH="/app/scripts:${PATH}"
# COPY ./scripts /app/scripts
# # RUN chmod +x /app/scripts/*

# # WORKDIR /apps
# WORKDIR /

# ENV PATH="/app/nemde:${PATH}"

# # RUN adduser user
# # RUN chown -R user:user /apps
# # RUN chmod -R 755 /apps
# # RUN chmod -R 755 /scripts
# # USER user

# CMD ["entrypoint.sh"]