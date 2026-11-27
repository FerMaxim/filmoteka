from django.contrib.auth.views import LoginView, LogoutView


class SignInView(LoginView):
    template_name = "accounts/login.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        response.status_code = 303
        return response

    def form_invalid(self, form):
        response = super().form_invalid(form)
        response.status_code = 422
        return response


class SignOutView(LogoutView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        response.status_code = 303
        return response
