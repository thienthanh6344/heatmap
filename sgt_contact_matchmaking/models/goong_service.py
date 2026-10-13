# -*- coding: utf-8 -*-
"""
Goong API Integration Service for Vietnam Geospatial Analytics.
Handles:
1. Forward Geocoding (Address -> Latitude, Longitude)
2. Place Autocomplete (Keyword -> Address suggestions)
3. Place Detail lookup
Safe error handling for 400, 401, 403, 429, 500, timeouts.
"""

import json
import logging
import os
import urllib.parse
import urllib.request
from odoo import _, api, models

_logger = logging.getLogger(__name__)

GOONG_GEOCODE_URL = "https://rsapi.goong.io/geocode"
GOONG_AUTOCOMPLETE_URL = "https://rsapi.goong.io/Place/AutoComplete"
GOONG_PLACE_DETAIL_URL = "https://rsapi.goong.io/Place/Detail"


class SgtGoongService(models.AbstractModel):
    _name = "sgt.goong.service"
    _description = "Goong Maps & Geocoding Service"

    @api.model
    def _get_api_key(self):
        """
        Retrieves Goong API Key from ir.config_parameter or OS environment.
        Never hard-coded.
        """
        key = self.env["ir.config_parameter"].sudo().get_param("sgt.goong.api_key")
        if not key:
            key = os.environ.get("GOONG_API_KEY", "")
        return (key or "").strip()

    @api.model
    def geocode_address(self, address, province=None, district=None, ward=None):
        """
        Geocodes a Vietnamese address into latitude and longitude using Goong Geocode API.
        :param address: Street address / Industrial zone
        :param province: Province or municipality name
        :param district: District name
        :param ward: Ward name
        :return: dict with status ('success'/'failed'), lat, lng, formatted_address, error message
        """
        api_key = self._get_api_key()
        if not api_key:
            return {
                "status": "failed",
                "error": _("Chưa cấu hình Goong API Key. Vui lòng cấu hình tham số 'sgt.goong.api_key' trong Cài đặt hệ thống."),
                "code": "MISSING_API_KEY",
            }

        # Build clean address string for Vietnam
        parts = [p for p in [address, ward, district, province, "Việt Nam"] if p and p.strip()]
        full_query = ", ".join(parts)

        params = {
            "address": full_query,
            "api_key": api_key,
        }
        url = f"{GOONG_GEOCODE_URL}?{urllib.parse.urlencode(params)}"

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Odoo19-Goong-Service/1.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                status_code = resp.status
                data = json.loads(resp.read().decode("utf-8"))

                if data.get("status") == "OK" and data.get("results"):
                    first_res = data["results"][0]
                    geometry = first_res.get("geometry", {})
                    location = geometry.get("location", {})
                    lat = location.get("lat")
                    lng = location.get("lng")

                    if lat is not None and lng is not None:
                        _logger.info("[Goong Geocoding] Successfully resolved '%s' -> (%f, %f)", full_query, lat, lng)
                        return {
                            "status": "success",
                            "lat": float(lat),
                            "lng": float(lng),
                            "formatted_address": first_res.get("formatted_address", full_query),
                            "query": full_query,
                        }

                error_msg = data.get("error_message") or _("Không tìm thấy tọa độ cho địa chỉ này.")
                return {
                    "status": "failed",
                    "error": error_msg,
                    "code": data.get("status", "NO_RESULTS"),
                    "query": full_query,
                }

        except urllib.error.HTTPError as http_err:
            _logger.warning("[Goong API HTTP Error] %s: %s", http_err.code, http_err.reason)
            if http_err.code in (401, 403):
                err_text = _("Goong API Key không hợp lệ hoặc không có quyền truy cập Geocode (Mã lỗi: %s).") % http_err.code
            elif http_err.code == 429:
                err_text = _("Vượt quá giới hạn lượt gọi Goong API (Rate Limit 429).")
            else:
                err_text = _("Lỗi kết nối máy chủ Goong API (Mã lỗi: %s).") % http_err.code
            return {"status": "failed", "error": err_text, "code": f"HTTP_{http_err.code}", "query": full_query}

        except urllib.error.URLError as url_err:
            _logger.error("[Goong Network Error] %s", url_err.reason)
            return {
                "status": "failed",
                "error": _("Không thể kết nối đến máy chủ Goong API (Hết thời gian chờ hoặc lỗi mạng)."),
                "code": "NETWORK_TIMEOUT",
                "query": full_query,
            }
        except Exception as ex:
            _logger.exception("[Goong Unexpected Exception] %s", ex)
            return {"status": "failed", "error": str(ex), "code": "EXCEPTION", "query": full_query}

    @api.model
    def autocomplete_address(self, input_text):
        """
        Searches address suggestions using Goong Place AutoComplete API.
        :param input_text: Search query string (e.g. 'YingBo Bình Dương')
        :return: list of suggestions
        """
        api_key = self._get_api_key()
        if not api_key or not input_text or len(input_text.strip()) < 2:
            return []

        params = {
            "input": input_text.strip(),
            "api_key": api_key,
            "limit": 6,
        }
        url = f"{GOONG_AUTOCOMPLETE_URL}?{urllib.parse.urlencode(params)}"

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Odoo19-Goong-Service/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("status") == "OK":
                    predictions = data.get("predictions", [])
                    return [
                        {
                            "place_id": p.get("place_id"),
                            "description": p.get("description"),
                            "main_text": p.get("structured_formatting", {}).get("main_text", ""),
                            "secondary_text": p.get("structured_formatting", {}).get("secondary_text", ""),
                            "compound": p.get("compound", {}),
                        }
                        for p in predictions
                    ]
        except Exception as ex:
            _logger.warning("[Goong Autocomplete Exception] %s", ex)

        return []

    @api.model
    def reverse_geocode(self, latitude, longitude):
        """
        Reverse geocodes coordinates into Vietnamese Ward, District, Province.
        Endpoint: https://rsapi.goong.io/Geocode?latlng={lat},{lng}&api_key={api_key}
        """
        api_key = self._get_api_key()
        if not api_key:
            return {
                "status": "failed",
                "error": _("Chưa cấu hình Goong API Key."),
                "code": "MISSING_API_KEY",
            }
        if latitude is None or longitude is None or (latitude == 0.0 and longitude == 0.0):
            return {
                "status": "failed",
                "error": _("Tọa độ không hợp lệ."),
                "code": "INVALID_COORDINATES",
            }

        params = {
            "latlng": f"{latitude},{longitude}",
            "api_key": api_key,
        }
        url = f"{GOONG_GEOCODE_URL}?{urllib.parse.urlencode(params)}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Odoo19-Goong-Service/1.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("status") == "OK" and data.get("results"):
                    first_res = data["results"][0]
                    compound = first_res.get("compound", {})
                    ward = compound.get("commune") or ""
                    district = compound.get("district") or ""
                    province = compound.get("province") or ""

                    if not (province and district):
                        for comp in first_res.get("address_components", []):
                            types = comp.get("types", [])
                            if "administrative_area_level_1" in types:
                                province = province or comp.get("long_name", "")
                            elif "administrative_area_level_2" in types:
                                district = district or comp.get("long_name", "")
                            elif "administrative_area_level_3" in types or "sublocality" in types:
                                ward = ward or comp.get("long_name", "")

                    return {
                        "status": "success",
                        "province": province,
                        "district": district,
                        "ward": ward,
                        "formatted_address": first_res.get("formatted_address", ""),
                    }
                return {
                    "status": "failed",
                    "error": data.get("error_message") or _("Không thể phân giải địa chỉ từ tọa độ."),
                    "code": data.get("status", "NO_RESULTS"),
                }
        except Exception as ex:
            _logger.warning("[Goong Reverse Geocoding Exception] %s", ex)
            return {"status": "failed", "error": str(ex), "code": "EXCEPTION"}
