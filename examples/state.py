import tgalice


TEXT_HELP = (
    'Привет! Я бот, который умеет работать и в Телеграме и в Алисе.'
    '\nПоскольку это пример, я просто повторяю ваши слова и считаю ваши сообщения.'
    '\nКогда вам надоест, скажите "довольно" или "Алиса, хватит".'
)
TEXT_FAREWELL = 'Всего доброго! Если захотите повторить, скажите "Алиса, включи навык тест tgalice".'


class ExampleDialogManager(tgalice.dialog_manager.BaseDialogManager):
    def respond(self, ctx):
        suggests = ['довольно']
        user_object = ctx.user_object
        count = user_object.get('count', -1) + 1
        commands = []
        text = tgalice.nlu.basic_nlu.fast_normalize(ctx.message_text)

        if not text or tgalice.nlu.basic_nlu.like_help(text) or not ctx.user_object or text == '/start':
            response = TEXT_HELP
        elif text == 'довольно' or tgalice.nlu.basic_nlu.like_exit(text):
            response = TEXT_FAREWELL
            commands.append(tgalice.dialog_manager.COMMANDS.EXIT)
        else:
            response = 'Вы только что сказали "{}". Всего вы сказали {}.'.format(ctx.message_text, self._count(count))

        user_object['count'] = count
        return tgalice.dialog_manager.Response(
            user_object=user_object, text=response, suggests=suggests, commands=commands
        )

    @staticmethod
    def _count(count):
        ones = count % 10
        tens = (count // 10) % 10
        if ones == 1 and tens != 1:
            return '{} команду'.format(count)
        elif ones in {2, 3, 4} and tens != 1:
            return '{} команды'.format(count)
        else:
            return '{} команд'.format(count)


if __name__ == '__main__':
    connector = tgalice.dialog_connector.DialogConnector(
        dialog_manager=ExampleDialogManager(),
        storage=tgalice.storage.session_storage.BaseStorage(),
        log_storage=tgalice.storage.message_logging.MongoMessageLogger()
    )
    server = tgalice.server.flask_server.FlaskServer(connector=connector)
    server.parse_args_and_run()
