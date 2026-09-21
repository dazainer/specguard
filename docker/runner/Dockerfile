FROM python:3.12.13-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2

LABEL io.specguard.runner.protocol="1" \
      io.specguard.runner.python="3.12.13" \
      io.specguard.runner.pytest="8.3.0" \
      io.specguard.runner.mutmut="2.4.4"

COPY requirements.lock /opt/specguard/requirements.lock
RUN python -m pip install --no-cache-dir --require-hashes --only-binary=:all: -r /opt/specguard/requirements.lock \
    && python -m pip check \
    && test -x /usr/bin/timeout
COPY build.lock mutation.lock /opt/specguard/
RUN python -m pip install --no-cache-dir --require-hashes --only-binary=:all: -r /opt/specguard/build.lock \
    && python -m pip install --no-cache-dir --no-build-isolation --require-hashes -r /opt/specguard/mutation.lock \
    && python -m pip check
COPY run_pytest.py mutation_inventory.py pytest.ini /opt/specguard/
RUN chmod -R a=rX /opt/specguard

USER 65532:65532
WORKDIR /scratch
ENTRYPOINT ["/usr/bin/timeout"]
