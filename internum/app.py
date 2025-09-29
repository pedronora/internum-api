from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from internum.api.main import router as main_router

app = FastAPI(title='Internum API - 1 RI Cascavel')

origins = [
    'http://localhost:5173',
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(main_router)
