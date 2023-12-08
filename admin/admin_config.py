import re
import socket

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from typing import List

from common.database import db_session
from common.formclass import ConfigForm
from common.models import Config
from lib.common import *
from lib.plugin.service import get_admin_plugin_menus, get_all_plugin_module_names


router = APIRouter()
templates = AdminTemplates()
# 파이썬 함수 및 변수를 jinja2 에서 사용할 수 있도록 등록
templates.env.globals["get_member_id_select"] = get_member_id_select
templates.env.globals["get_skin_select"] = get_skin_select
templates.env.globals["get_editor_select"] = get_editor_select
templates.env.globals["get_member_level_select"] = get_member_level_select
templates.env.globals["option_array_checked"] = option_array_checked
templates.env.globals["get_admin_plugin_menus"] = get_admin_plugin_menus
templates.env.globals["get_all_plugin_module_names"] = get_all_plugin_module_names


CONFIG_MENU_KEY = "100100"


@router.get("/config_form")
async def config_form(request: Request):
    """
    기본환경설정 폼
    """
    request.session["menu_key"] = CONFIG_MENU_KEY

    if not request.state.is_super_admin:
        raise AlertException("최고관리자만 접근 가능합니다.")

    host_name = socket.gethostname()
    host_ip = socket.gethostbyname(host_name)
    client_ip = get_client_ip(request)

    return templates.TemplateResponse(
        "config_form.html",
        {
            "request": request,
            "config": request.state.config,
            "host_name": host_name,
            "host_ip": host_ip,
            "client_ip": client_ip,
        },
    )


@router.post("/config_form_update", dependencies=[Depends(validate_token)])
async def config_form_update(
        request: Request,
        db: db_session,
        social_list: List[str] = Form(None, alias="cf_social_servicelist[]"),
        form_data: ConfigForm = Depends(),
):
    """
    기본환경설정 저장
    """
    if not request.state.is_super_admin:
        raise AlertException("최고관리자만 접근 가능합니다.")

    # 차단 IP 리스트에 현재 접속 IP 가 있으면 접속이 불가하게 되므로 저장하지 않는다.
    if form_data.cf_intercept_ip:
        client_ip = get_client_ip(request)
        pattern = form_data.cf_intercept_ip.split("\n")
        for i in range(len(pattern)):
            pattern[i] = pattern[i].strip()
            if not pattern[i]:
                continue
            pattern[i] = pattern[i].replace(".", "\.")
            pattern[i] = pattern[i].replace("+", "[0-9\.]+", pattern[i])
            if re.match("/^{$pattern[$i]}$/", client_ip):
                raise AlertException("현재 접속 IP : " + client_ip + " 가 차단될수 있으므로 다른 IP를 입력해 주세요.")

    # 본인인증 설정 체크
    if (form_data.cf_cert_use 
        and not any([form_data.cf_cert_ipin, form_data.cf_cert_hp, form_data.cf_cert_simple])):
        raise AlertException("본인확인을 위해 아이핀, 휴대폰 본인확인, KG이니시스 간편인증 서비스 중 하나 이상 선택해 주십시오.")

    if not form_data.cf_cert_use:
        form_data.cf_cert_ipin = form_data.cf_cert_hp = form_data.cf_cert_simple = ""

    # 소셜로그인 설정
    # 배열로 넘어오는 자료를 문자열로 변환. 예) "naver,kakao,facebook,google,twitter,payco"
    form_data.cf_social_servicelist = ','.join(social_list) if social_list else ""

    # 폼 데이터 반영 후 commit
    config = db.query(Config).first()
    for field, value in form_data.__dict__.items():
        setattr(config, field, value)
    db.commit()

    return RedirectResponse("/admin/config_form", status_code=303)