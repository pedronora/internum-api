from fastapi import FastAPI

from internum.api.main import router as main_router

app = FastAPI(title='Internum API - 1 RI Cascavel')


app.include_router(main_router)
