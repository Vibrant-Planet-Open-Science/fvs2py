FROM daviddanieldiaz/fvs:FS2024.4

RUN groupadd -g 1000 fvs2py-dev && \
    useradd -m -u 1000 -g fvs2py-dev fvs2py-dev
RUN chown fvs2py-dev:fvs2py-dev /home/fvs2py-dev
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt && rm requirements.txt
USER fvs2py-dev