
from fastapi import APIRouter, Depends, Form, status
from fastapi.security import HTTPAuthorizationCredentials

from app.core.dn.dependencies import bearer_scheme, get_current_user
from app.schemas.dn.auth_schema import SigninResponse, SignupRequest, UserPublic
from app.services.dn import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", status_code=status.HTTP_201_CREATED, response_model=UserPublic)
async def signup_route(payload: SignupRequest) -> UserPublic:
    return auth_service.signup(payload)


@router.post("/signin", response_model=SigninResponse)
async def signin_route(
    email: str = Form(...),
    password: str = Form(...),
) -> SigninResponse:
    return auth_service.signin(email=email, password=password)


@router.post("/signout", status_code=status.HTTP_204_NO_CONTENT)
async def signout_route(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    current_user: dict = Depends(get_current_user),
) -> None:
    auth_service.signout(credentials.credentials)
