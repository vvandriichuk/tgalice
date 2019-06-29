import re
import yaml

from collections import Mapping

from .base import CascadableDialogManager, Context, Response
from ..nlu import basic_nlu, matchers


class FieldConfig:
    def __init__(self, obj, idx=-1):
        self.validate_regexp = re.compile(obj.get('validate_regexp', '.*'))
        self.id = id
        self.name = obj.get('name', 'field_{}'.format(idx))
        self.question = obj['question']
        self.validate_message = obj.get('validate_message')
        self.options = obj.get('options')
        self.suggests = obj.get('suggests')

        if self.options is not None:
            self.matcher = matchers.make_matcher(**obj.get('matching', {'key': 'levenshtein', 'threshold': 0.8}))
            self.matcher.fit(self.options, self.options)
        else:
            self.matcher = None


class FormConfig:
    def __init__(self, config):
        if isinstance(config, str):
            with open(config, 'r', encoding='utf-8') as f:
                self._cfg = yaml.load(f)
        elif isinstance(config, Mapping):
            self._cfg = config
        else:
            raise ValueError('Config should be a yaml filename or a dict')
        # todo: validate everything
        self.form_name = self._cfg['form_name']

        self.start_regex = re.compile(self._cfg['start'].get('regexp', '.*'))
        self.start_message = self._cfg['start'].get('message')
        self.start_suggests = self._cfg['start'].get('suggests', [])

        exit_block = self._cfg.get('exit', {})
        self.exit_regexp = re.compile(exit_block['regexp']) if 'regexp' in exit_block else None
        self.exit_message = exit_block.get('message')
        self.exit_suggest = exit_block.get('suggest')

        self.finish_message = self._cfg.get('finish', {}).get('message')

        self.fields = [FieldConfig(obj, idx=i) for i, obj in enumerate(self._cfg['fields'])]
        self.default_field = FieldConfig(self._cfg['default_field']) if 'default_field' in self._cfg else None
        self.num_fields = len(self.fields)


class FormFillingDialogManager(CascadableDialogManager):
    def __init__(self, config, *args, **kwargs):
        super(FormFillingDialogManager, self).__init__(*args, **kwargs)
        self.config = FormConfig(config)

    def try_to_respond(self, ctx: Context):
        user_object = ctx.user_object
        normalized = basic_nlu.fast_normalize(ctx.message_text)
        form = user_object.get('forms', {}).get(self.config.form_name, {})
        if form.get('is_active'):
            if self.config.exit_regexp and re.match(self.config.exit_regexp, normalized):
                form['is_active'] = False
                return Response(text=self.config.exit_message, user_object=user_object)
            question_id = form['next_question']
            validated_answer = self.validate_answer(form, ctx.message_text)
            if validated_answer is not None:
                form['fields'][self.config.fields[question_id].name] = validated_answer
                next_question_id = question_id + 1
                if next_question_id >= self.config.num_fields:
                    form['is_active'] = False
                    result = self.handle_completed_form(form, ctx)
                    if result is not None:
                        return result
                    return Response(text=self.config.finish_message, user_object=user_object)
                form['next_question'] = next_question_id
                return self.ask_question(next_question_id, user_object=user_object, reask=False)
            else:
                return self.ask_question(question_id, user_object=user_object, reask=True)
        elif re.match(self.config.start_regex, normalized):
            if 'forms' not in user_object:
                user_object['forms'] = {}
            # todo: if there is no start message, move directly to question 0
            user_object['forms'][self.config.form_name] = {
                'fields': {},
                'is_active': True,
                'next_question': -1
            }
            form = user_object['forms'][self.config.form_name]
            if self.config.start_message is not None:
                form['next_question'] = -1
                return Response(
                    text=self.config.start_message, suggests=self.config.start_suggests, user_object=user_object
                )
            else:
                form['next_question'] = 0
                return self.ask_question(0, user_object, reask=False)
        return None

    def ask_question(self, next_question_id, user_object, reask=False):
        the_question = self.config.fields[next_question_id]
        response = the_question.question
        if reask:
            if the_question.validate_message is not None:
                response = the_question.validate_message
            elif 'validate_message' in self.config.default_field:
                response = self.config.default_field['validate_message']
        if the_question.options is not None:
            suggests = the_question.options
        elif the_question.suggests is not None:
            suggests = the_question.suggests
        else:
            suggests = []
        if self.config.exit_suggest is not None:
            suggests.append(self.config.exit_suggest)
        return Response(user_object=user_object, text=response, suggests=suggests)

    def validate_answer(self, form, message_text):
        question_id = form.get('next_question', -1)
        if question_id == -1:
            return message_text
        the_question = self.config.fields[question_id]
        normalized_text = basic_nlu.fast_normalize(message_text)
        if the_question.options is not None:
            winner_label, best_score = the_question.matcher.match(message_text)
            return winner_label
        if the_question.validate_regexp is not None:
            if re.match(the_question.validate_regexp, normalized_text):
                return message_text
            else:
                return None
        return message_text

    def handle_completed_form(self, form, ctx):
        """ This method can be overwritten to do something useful """
        return None
